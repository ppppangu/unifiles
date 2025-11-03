import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from loguru import logger
from openai import AsyncOpenAI, OpenAI

from ...database import extraction_db_manager
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
        total_assets = 0
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
                            full_texts.append(
                                f"\n![{category}](picture_{i}_{index}.png)\n"
                            )
                            index += 1
                            total_assets += 1

                        else:
                            text = el.get("text", "")
                            full_texts.append(f"\n{text}\n")

                    index = 0
                    full_texts.append("\n\n---\n\n")

                    # TODO: 遵循simple模式下类似流程，将文件上传到文件存储服务

                except Exception as e:
                    logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                    continue
        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return ""
        markdown_text = "".join(full_texts)

        # 参照 simple mode，将全文本入库 extracted_documents
        try:
            self._persist_markdown_to_db_sync(
                markdown=markdown_text,
                pdf_path=pdf_path,
                total_pages=len(images) if "images" in locals() else 0,
                total_assets=total_assets,
            )
        except Exception as e:
            logger.warning(f"Persisting markdown to DB failed: {e!s}")

        return markdown_text

    def _persist_markdown_to_db_sync(
        self,
        markdown: str,
        pdf_path: Path,
        total_pages: int,
        total_assets: int,
    ) -> Optional[str]:
        """在同步环境中将 Markdown 文本持久化到 Postgres。

        说明：
        - 参考 DocumentProcessingService 的 simple 模式入库流程：
          创建/获取策略 -> 写入 extracted_documents。
        - 由于 provider 层无 file_id/user_id 上下文，这里使用可追踪占位符。
        """

        async def _persist() -> Optional[str]:
            try:
                strategy_id = (
                    await extraction_db_manager.create_or_get_processing_strategy(
                        strategy_name="OCR-selfhosted",
                        strategy_type="ocr",
                        processing_config={
                            "method": "selfhosted",
                            "version": "1.0.0",
                            "engine": self.config.get_model(),
                        },
                    )
                )

                file_id = f"local:{pdf_path.name}"
                user_id = "system"

                extraction_id = await extraction_db_manager.create_extracted_document(
                    file_id=file_id,
                    user_id=user_id,
                    extraction_strategy_id=strategy_id,
                    full_markdown=markdown,
                    total_pages=total_pages,
                    total_chars=len(markdown),
                    total_assets=total_assets,
                    extraction_metadata={
                        "source": "selfhosted_sync",
                        "pdf_path": str(pdf_path),
                    },
                    extraction_status="completed",
                )
                logger.info(
                    f"Persisted extracted document to DB: {extraction_id} (file={file_id})"
                )
                return extraction_id
            except Exception as e:
                logger.warning(f"DB persistence coroutine failed: {e!s}")
                return None

        try:
            return asyncio.run(_persist())
        except RuntimeError:
            import threading

            result: dict = {}

            def runner():
                try:
                    result["extraction_id"] = asyncio.run(_persist())
                except Exception as inner_e:
                    logger.warning(f"Threaded DB persistence failed: {inner_e!s}")

            t = threading.Thread(target=runner, daemon=True)
            t.start()
            t.join()
            return result.get("extraction_id")

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

                # Parse and reconstruct text/crops. Run parsing and cropping in threads.
                def parse_and_extract() -> Tuple[str, List[Dict[str, Any]]]:
                    out_parts: List[str] = []
                    page_images_info: List[Dict[str, Any]] = []

                    # Determine output directory
                    if output_dir is None:
                        save_dir = Path.cwd()
                    else:
                        save_dir = output_dir
                        save_dir.mkdir(parents=True, exist_ok=True)

                    try:
                        json_dict = self._extract_json_from_markdown(
                            json_markdown.strip()
                        )
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
                                filename = f"picture_{page_num}_{index}.png"
                                img_path = save_dir / filename
                                img_crop.save(str(img_path))

                                # Collect image metadata
                                page_images_info.append(
                                    {
                                        "page": page_num - 1,  # Convert to 0-indexed
                                        "index": index,
                                        "filename": filename,
                                        "path": str(img_path),
                                        "extension": "png",
                                        "size_bytes": os.path.getsize(str(img_path))
                                        if img_path.exists()
                                        else 0,
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
                    return "".join(out_parts), page_images_info

                page_text, page_images = await asyncio.to_thread(parse_and_extract)

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
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Async process for local file.

        Args:
            file_path: Path to the file to process
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

        # PDF handling with async parallel processing
        if p.suffix.lower() == ".pdf":
            return await self._process_pdf_async(p, output_dir, progress_callback)

        # Image handling (no images to extract from single image OCR)
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return "", []

        messages = self._build_request_payload(p)
        if not messages:
            logger.error(f"Failed to build request for {p}")
            return "", []
        try:
            client = self._get_async_client()
            resp = await client.chat.completions.create(
                model=self.config.get_model(),
                messages=messages,
                temperature=self.config.get_temperature(),
                max_tokens=self.config.get_max_tokens(),
            )
            return resp.choices[0].message.content or "", []
        except Exception as e:
            logger.error(f"Self-hosted async request failed: {e!s}")
            return "", []
