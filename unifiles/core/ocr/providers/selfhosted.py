import asyncio
import base64
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import json
import re
from loguru import logger
from openai import AsyncOpenAI, OpenAI

from ..base import BaseOCRProvider
from ..config.selfhosted import SelfHostedConfig
from ..utils.parser import load_images_from_pdf, to_rgb


class SelfHostedOCRProvider(BaseOCRProvider):
    """Self-hosted OCR provider (OpenAI-compatible).

    This trimmed version keeps only process_file and its required helpers.
    """

    def __init__(self, config: Optional[SelfHostedConfig] = None):
        super().__init__(config or SelfHostedConfig())

    def get_provider_name(self) -> str:
        return "selfhosted"

    def _process_image_for_model(self, image, factor: int = 8) -> Optional[str]:
        """Convert PIL Image or path to base64-encoded PNG suitable for model."""
        try:
            import io
            from PIL import Image as PILImage

            # Load image if it's a path
            if isinstance(image, (str, Path)):
                pil_image = PILImage.open(image)
            else:
                pil_image = image

            # Convert to RGB (handle RGBA with white background)
            pil_image = to_rgb(pil_image)

            # Convert to base64 PNG
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG", optimize=False)
            base64_image = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
            return base64_image
        except Exception as e:
            logger.error(f"Failed to process image for model: {e!s}")
            return None

    def _build_request_payload(self, image_path: Path) -> Optional[list]:
        """Build Chat Completions messages with base64 image and prompt."""
        base64_image = self._process_image_for_model(image_path)
        if not base64_image:
            return None
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                    },
                    {"type": "text", "text": self.config.get_prompt()},
                ],
            }
        ]

    def _normalize_base_url(self, url: str) -> str:
        suffix = "/chat/completions"
        if url.endswith(suffix):
            return url[: -len(suffix)]
        return url.rstrip("/")

    def _get_sync_client(self) -> OpenAI:
        base_url = self._normalize_base_url(self.config.get_url())
        api_key = self.config.get_api_key() or "no-key"
        return OpenAI(api_key=api_key, base_url=base_url)

    def _get_async_client(self) -> AsyncOpenAI:
        base_url = self._normalize_base_url(self.config.get_url())
        api_key = self.config.get_api_key() or "no-key"
        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _send_request(self, messages: list) -> str:
        """Sync request via OpenAI SDK; returns text content."""
        try:
            client = self._get_sync_client()
            resp = client.chat.completions.create(
                model=self.config.get_model(),
                messages=messages,
                temperature=self.config.get_temperature(),
                max_tokens=self.config.get_max_tokens(),
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Self-hosted sync request failed: {e!s}")
            return ""

    def _process_pdf(self, pdf_path: Path) -> str:
        """Render PDF pages to images using parser and OCR each page."""
        full_texts: List[str] = []
        try:
            images = load_images_from_pdf(str(pdf_path))
            for i, img in enumerate(images):
                try:
                    base64_image = self._process_image_for_model(img)
                    if not base64_image:
                        logger.warning(f"Failed to process image for page {i + 1}")
                        continue
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                                },
                                {"type": "text", "text": self.config.get_prompt()},
                            ],
                        }
                    ]
                    json_markdown = self._send_request(messages)
                    json_dict = self._extract_json_from_markdown(json_markdown.strip())
                    index = 0
                    for el in json_dict.get("layout_elements", []):
                        bbox = el["bbox"]
                        abs_y1 = int(bbox[1] / 999 * img.height)
                        abs_x1 = int(bbox[0] / 999 * img.width)
                        abs_y2 = int(bbox[3] / 999 * img.height)
                        abs_x2 = int(bbox[2] / 999 * img.width)

                        category = el["category"]
                    
                        # 切分图片
                        if category == "Picture":
                            # 切分图片
                            img_crop = img.crop((abs_x1, abs_y1, abs_x2, abs_y2))
                            img_crop.save(f"picture_{i}_{index}.png")
                            full_texts.append(f"\n![{category}](picture_{i}_{index}.png)\n")
                            index += 1
                        
                        else:
                            text = el.get("text", "")
                            full_texts.append(f"\n{text}\n")
        
                    index = 0
                    full_texts.append("\n\n---\n\n")

                    # TODO: 将文件上传到文件存储服务并更新postgres



                except Exception as e:
                    logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                    continue
        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return ""
        return "".join(full_texts)

    # --------------------
    # Async helpers and PDF processing with concurrency
    # --------------------
    async def _send_request_async(self, messages: list) -> str:
        """Async request via OpenAI-compatible SDK; returns text content."""
        client = self._get_async_client()
        resp = await client.chat.completions.create(
            model=self.config.get_model(),
            messages=messages,
            temperature=self.config.get_temperature(),
            max_tokens=self.config.get_max_tokens(),
        )
        try:
            return resp.choices[0].message.content or ""
        except Exception:
            logger.warning("Self-hosted async response has no content")
            return ""

    async def _send_request_with_retry(self, messages: list, page_num: int) -> Tuple[int, str]:
        """Send request with retries; returns (page_num, text)."""
        max_retries = max(0, int(self.config.get_max_retries()))
        for attempt in range(max_retries + 1):
            try:
                text = await self._send_request_async(messages)
                if attempt > 0:
                    logger.info(f"Page {page_num} succeeded after {attempt} retries")
                return (page_num, text)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Page {page_num} failed after {max_retries} retries: {e!s}"
                    )
                    return (page_num, "")
                wait_time = 2**attempt
                logger.warning(
                    f"Page {page_num} attempt {attempt + 1} failed, retrying in {wait_time}s: {e!s}"
                )
                await asyncio.sleep(wait_time)
        return (page_num, "")

    async def _process_single_page_async(
        self,
        page_num: int,
        img,
        semaphore: asyncio.Semaphore,
        total_pages: int,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[int, str]:
        """Process a single page image concurrently; returns (page_num, text)."""
        async with semaphore:
            try:
                if progress_callback:
                    progress_callback(
                        page_num, total_pages, "processing", f"Processing page {page_num}/{total_pages}"
                    )

                # Encode image to base64 in a thread to avoid blocking loop
                base64_image = await asyncio.to_thread(self._process_image_for_model, img)
                if not base64_image:
                    if progress_callback:
                        progress_callback(
                            page_num, total_pages, "failed", f"Image encode failed for page {page_num}"
                        )
                    return (page_num, "")

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                            {"type": "text", "text": self.config.get_prompt()},
                        ],
                    }
                ]

                # Request with retries
                _, json_markdown = await self._send_request_with_retry(messages, page_num)
                if not json_markdown:
                    if progress_callback:
                        progress_callback(
                            page_num, total_pages, "failed", f"No content for page {page_num}"
                        )
                    return (page_num, "")

                # Parse and reconstruct text/crops. Run parsing and cropping in threads.
                def parse_and_extract() -> str:
                    out_parts: List[str] = []
                    try:
                        json_dict = self._extract_json_from_markdown(json_markdown.strip())
                        index = 0
                        for el in json_dict.get("layout_elements", []):
                            bbox = el["bbox"]
                            abs_y1 = int(bbox[1] / 999 * img.height)
                            abs_x1 = int(bbox[0] / 999 * img.width)
                            abs_y2 = int(bbox[3] / 999 * img.height)
                            abs_x2 = int(bbox[2] / 999 * img.width)

                            category = el["category"]

                            if category == "Picture":
                                img_crop = img.crop((abs_x1, abs_y1, abs_x2, abs_y2))
                                img_crop.save(f"picture_{page_num}_{index}.png")
                                out_parts.append(f"\n![{category}](picture_{page_num}_{index}.png)\n")
                                index += 1
                            else:
                                text = el.get("text", "")
                                out_parts.append(f"\n{text}\n")
                    except Exception as e:
                        logger.warning(f"Failed to parse page {page_num} result: {e!s}")
                    # Page separator
                    out_parts.append("\n\n---\n\n")
                    return "".join(out_parts)

                page_text = await asyncio.to_thread(parse_and_extract)

                if progress_callback:
                    progress_callback(
                        page_num, total_pages, "completed", f"Completed page {page_num}/{total_pages}"
                    )
                return (page_num, page_text)

            except Exception as e:
                logger.error(f"Failed to process page {page_num}: {e!s}")
                if progress_callback:
                    progress_callback(
                        page_num, total_pages, "failed", f"Error processing page {page_num}: {e!s}"
                    )
                return (page_num, "")

    async def _process_pdf_async(
        self,
        pdf_path: Path,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> str:
        """Render PDF pages to images and OCR each page concurrently."""
        try:
            images = load_images_from_pdf(str(pdf_path))
            if not images:
                logger.error("No pages were rendered from PDF")
                return ""

            max_concurrency = max(1, int(self.config.get_max_concurrency()))
            semaphore = asyncio.Semaphore(max_concurrency)
            total_pages = len(images)
            logger.info(
                f"[SelfHosted OCR] Processing {total_pages} pages with concurrency={max_concurrency}"
            )

            tasks = [
                self._process_single_page_async(i + 1, img, semaphore, total_pages, progress_callback)
                for i, img in enumerate(images)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect and sort by page number
            ordered: List[Tuple[int, str]] = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Task failed with exception: {r!s}")
                    continue
                if isinstance(r, tuple) and len(r) == 2:
                    ordered.append(r)

            ordered.sort(key=lambda x: x[0])
            return "".join(text for _, text in ordered if text)

        except Exception as e:
            logger.error(f"Async PDF processing failed: {e!s}")
            return ""

    def _extract_json_from_markdown(self, markdown: str) -> str:
        """Extract JSON string from markdown using regex."""
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', markdown, re.S)
        if not json_match:
            json_match = re.search(r'(\{.*\})', markdown, re.S)
        if json_match:
            json_dict = json.loads(json_match.group(1))
            return json_dict
        return ""

    def process_url(self, url: str) -> str:
        logger.warning(
            "URL processing not supported for OpenAI-compatible format. "
            "Please download the file and use process_file() instead."
        )
        return ""

    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process local file with OCR (PDF per-page; images direct)."""
        if not self.config.validate():
            return ""
        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""
        if p.suffix.lower() == ".pdf":
            return self._process_pdf(p)
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""
        payload = self._build_request_payload(p)
        if not payload:
            logger.error(f"Failed to build request for {p}")
            return ""
        return self._send_request(payload)

    # --------------------
    # Async public API
    # --------------------
    async def aprocess_file(
        self,
        file_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> str:
        """Async process for local file.

        - PDF: concurrent page processing using AsyncOpenAI client
        - Image: single request via async client
        """
        if not self.config.validate():
            return ""

        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""

        # PDF handling with async parallel processing
        if p.suffix.lower() == ".pdf":
            return await self._process_pdf_async(p, progress_callback)

        # Image handling
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""

        messages = self._build_request_payload(p)
        if not messages:
            logger.error(f"Failed to build request for {p}")
            return ""
        try:
            client = self._get_async_client()
            resp = await client.chat.completions.create(
                model=self.config.get_model(),
                messages=messages,
                temperature=self.config.get_temperature(),
                max_tokens=self.config.get_max_tokens(),
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Self-hosted async request failed: {e!s}")
            return ""
