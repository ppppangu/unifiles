import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from loguru import logger
from openai import AsyncOpenAI, OpenAI

from ..base import BaseOCRProvider
from ..config.selfhosted import SelfHostedConfig
from ..utils.parser import load_images_from_pdf, to_rgb


class SelfHostedOCRProvider(BaseOCRProvider):
    """Self-hosted OCR provider (OpenAI-compatible) for PDF processing.

    This provider processes PDF files only with support for both sync and async operations.
    Features:
    - Concurrent page processing with configurable concurrency
    - Automatic retry mechanism with exponential backoff
    - In-memory image handling (no disk I/O)
    - Progress callback support for async operations
    """

    def __init__(self, config: Optional[SelfHostedConfig] = None):
        super().__init__(config or SelfHostedConfig())
        # Initialize OpenAI clients
        base_url = self._normalize_base_url(self.config.get_url())
        api_key = self.config.get_api_key() or "no-key"
        self._sync_client = OpenAI(api_key=api_key, base_url=base_url)
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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


    def _normalize_base_url(self, url: str) -> str:
        suffix = "/chat/completions"
        if url.endswith(suffix):
            return url[: -len(suffix)]
        return url.rstrip("/")

    def _send_request(self, messages: list) -> str:
        """Sync request via OpenAI SDK; returns text content."""
        try:
            resp = self._sync_client.chat.completions.create(
                model=self.config.get_model(),
                messages=messages,
                temperature=self.config.get_temperature(),
                max_tokens=self.config.get_max_tokens(),
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Self-hosted sync request failed: {e!s}")
            return ""

    def _process_pdf(self, pdf_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Render PDF pages to images using parser and OCR each page.

        Returns:
            Tuple[str, List[Dict]]: (markdown_text, images_info)
        """

        full_texts: List[str] = []
        all_images_info: List[Dict[str, Any]] = []

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
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    },
                                },
                                {"type": "text", "text": self.config.get_prompt()},
                            ],
                        }
                    ]
                    json_markdown = self._send_request(messages)

                    # Unified parsing and extraction via class method
                    page_text, page_images = self._parse_and_extract(
                        json_markdown, img, i + 1
                    )
                    full_texts.append(page_text)
                    all_images_info.extend(page_images)

                except Exception as e:
                    logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                    continue
        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return "", []

        markdown_text = "".join(full_texts)
        logger.info(
            f"[SelfHosted OCR Sync] Processing completed: {len(markdown_text)} chars, "
            f"{len(all_images_info)} images (memory only, no disk I/O)"
        )
        return markdown_text, all_images_info

    # --------------------
    # Async helpers and PDF processing with concurrency
    # --------------------
    async def _send_request_async(self, messages: list) -> str:
        """Async request via OpenAI-compatible SDK; returns text content."""
        resp = await self._async_client.chat.completions.create(
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

    async def _send_request_with_retry(
        self, messages: list, page_num: int
    ) -> Tuple[int, str]:
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
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[int, str, List[Dict[str, Any]]]:
        """Process a single page image concurrently; returns (page_num, text, images_info)."""
        async with semaphore:
            try:
                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "processing",
                        f"Processing page {page_num}/{total_pages}",
                    )

                # Encode image to base64 in a thread to avoid blocking loop
                base64_image = await asyncio.to_thread(
                    self._process_image_for_model, img
                )
                if not base64_image:
                    if progress_callback:
                        progress_callback(
                            page_num,
                            total_pages,
                            "failed",
                            f"Image encode failed for page {page_num}",
                        )
                    return (page_num, "")

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                            {"type": "text", "text": self.config.get_prompt()},
                        ],
                    }
                ]

                # Request with retries
                _, json_markdown = await self._send_request_with_retry(
                    messages, page_num
                )
                if not json_markdown:
                    if progress_callback:
                        progress_callback(
                            page_num,
                            total_pages,
                            "failed",
                            f"No content for page {page_num}",
                        )
                    return (page_num, "")

                # Parse and reconstruct text/crops via class method in a thread.
                page_text, page_images = await asyncio.to_thread(
                    self._parse_and_extract, json_markdown, img, page_num
                )

                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "completed",
                        f"Completed page {page_num}/{total_pages}",
                    )
                return (page_num, page_text, page_images)

            except Exception as e:
                logger.error(f"Failed to process page {page_num}: {e!s}")
                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "failed",
                        f"Error processing page {page_num}: {e!s}",
                    )
                return (page_num, "", [])

    async def _process_pdf_async(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Render PDF pages to images and OCR each page concurrently.

        Returns:
            Tuple[str, List[Dict]]: (markdown_text, images_info)
        """
        try:
            images = load_images_from_pdf(str(pdf_path))
            if not images:
                logger.error("No pages were rendered from PDF")
                return "", []

            # Create output directory if not specified
            if output_dir is None:
                output_dir = Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)

            max_concurrency = max(1, int(self.config.get_max_concurrency()))
            semaphore = asyncio.Semaphore(max_concurrency)
            total_pages = len(images)
            logger.info(
                f"[SelfHosted OCR] Processing {total_pages} pages with concurrency={max_concurrency}"
            )

            tasks = [
                self._process_single_page_async(
                    i + 1, img, semaphore, total_pages, output_dir, progress_callback
                )
                for i, img in enumerate(images)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect and sort by page number
            ordered: List[Tuple[int, str, List[Dict[str, Any]]]] = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Task failed with exception: {r!s}")
                    continue
                if isinstance(r, tuple) and len(r) == 3:
                    ordered.append(r)

            ordered.sort(key=lambda x: x[0])

            # Combine text and collect all images
            all_images_info: List[Dict[str, Any]] = []
            markdown_text = "".join(text for _, text, _ in ordered if text)
            for _, _, page_images in ordered:
                all_images_info.extend(page_images)

            logger.info(
                f"[SelfHosted OCR] Processing completed: {len(markdown_text)} chars, {len(all_images_info)} images"
            )
            return markdown_text, all_images_info

        except Exception as e:
            logger.error(f"Async PDF processing failed: {e!s}")
            return "", []

    def _parse_and_extract(
        self, json_markdown: str, img, page_num: int
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Parse model JSON markdown and extract text and in-memory image crops.

        Returns a tuple of (markdown_text, images_info) for a single page.
        """
        import io  # For BytesIO

        out_parts: List[str] = []
        page_images_info: List[Dict[str, Any]] = []

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

                if category in ["Picture", "Table"]:
                    img_crop = img.crop((abs_x1, abs_y1, abs_x2, abs_y2))
                    # Use category name as filename prefix
                    prefix = category.lower()
                    filename = f"{prefix}_{page_num}_{index}.png"

                    # Save to memory instead of disk
                    img_buffer = io.BytesIO()
                    img_crop.save(img_buffer, format="PNG", optimize=False)
                    img_bytes = img_buffer.getvalue()
                    img_buffer.close()

                    # Collect image metadata (with bytes data)
                    page_images_info.append(
                        {
                            "page": page_num - 1,  # Convert to 0-indexed
                            "index": index,
                            "filename": filename,
                            "bytes": img_bytes,  # Store bytes instead of path
                            "extension": "png",
                            "size_bytes": len(img_bytes),
                        }
                    )

                    out_parts.append(f"\n![{category}]({filename})\n")
                    index += 1
                else:
                    text = el.get("text", "")
                    out_parts.append(f"\n{text}\n")
        except Exception as e:
            logger.warning(f"Failed to parse page {page_num} result: {e!s}")

        # Page separator
        out_parts.append("\n\n---\n\n")

        # 保存处理的结果用于调试
        with open(f"debug_page_{page_num}.json", "w", encoding="utf-8") as f:
            json.dump(json_dict, f, indent=2, ensure_ascii=False)

        return "".join(out_parts), page_images_info

    def _extract_json_from_markdown(self, markdown: str) -> str:
        """Extract JSON string from markdown using regex."""
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", markdown, re.S)
        if not json_match:
            json_match = re.search(r"(\{.*\})", markdown, re.S)
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
        """Process local PDF file with OCR.

        Note: This method only returns markdown text for backward compatibility.
        For images_info, use aprocess_file() instead.
        """
        if not self.config.validate():
            return ""
        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""
        if p.suffix.lower() != ".pdf":
            logger.error(f"Only PDF files are supported, got: {p.suffix}")
            return ""
        # _process_pdf now returns (text, images_info), extract only text
        markdown_text, _ = self._process_pdf(p)
        return markdown_text

    # --------------------
    # Async public API
    # --------------------

    async def aprocess_file(
        self,
        file_path: Union[str, Path],
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Async process for local PDF file.

        Args:
            file_path: Path to the PDF file to process
            output_dir: Directory to save extracted images (default: current directory)
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple[str, List[Dict]]: (markdown_text, images_info)
                - markdown_text: Extracted text in markdown format
                - images_info: List of image metadata dictionaries
        """
        if not self.config.validate():
            return "", []

        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return "", []

        if p.suffix.lower() != ".pdf":
            logger.error(f"Only PDF files are supported, got: {p.suffix}")
            return "", []

        # PDF handling with async parallel processing
        return await self._process_pdf_async(p, output_dir, progress_callback)
