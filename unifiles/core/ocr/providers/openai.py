import asyncio
import base64
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

from loguru import logger
from openai import AsyncOpenAI, OpenAI

from ..base import BaseOCRProvider
from ..config.openai import OpenAIConfig


class OpenAIOCRProvider(BaseOCRProvider):
    """OCR provider using OpenAI async SDK (Chat Completions)."""

    def __init__(self, config: Optional[OpenAIConfig] = None):
        super().__init__(config or OpenAIConfig())

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        return "openai"

    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """Encode image file to base64 string."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e!s}")
            return None

    def _build_request_payload(self, image_path: Path) -> Optional[list]:
        """Build Chat Completions messages with base64 image and prompt."""
        base64_image = self._encode_image_to_base64(image_path)
        if not base64_image:
            return None

        ext = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        },
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
        return OpenAI(api_key=self.config.get_api_key(), base_url=base_url)

    def _get_async_client(self) -> AsyncOpenAI:
        base_url = self._normalize_base_url(self.config.get_url())
        return AsyncOpenAI(api_key=self.config.get_api_key(), base_url=base_url)

    def _send_request(self, payload: list) -> str:
        """Sync request via OpenAI SDK; returns text content."""
        try:
            client = self._get_sync_client()
            resp = client.chat.completions.create(
                model=self.config.get_model(), messages=payload
            )
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                return resp.choices[0].message.content
            logger.warning("OpenAI response has no content")
            return ""
        except Exception as e:
            logger.error(f"OpenAI sync request failed: {e!s}")
            return ""

    # --------------------
    # Public API
    # --------------------
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process local file with OCR.

        For PDFs: renders pages to images and processes each page
        For images: processes directly

        Args:
            file_path: Path to the file

        Returns:
            Extracted text in Markdown format
        """
        if not self.config.validate():
            return ""

        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""

        # PDF handling
        if p.suffix.lower() == ".pdf":
            return self._process_pdf(p)

        # Image handling
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""

        payload = self._build_request_payload(p)
        if not payload:
            logger.error(f"Failed to build request for {p}")
            return ""

        return self._send_request(payload)

    def process_url(self, url: str) -> str:
        """Process file from URL with OCR.

        Note: OpenAI-compatible API expects base64 encoded images,
        so URL processing is not supported. Download the file first
        and use process_file() instead.
        """
        logger.warning(
            "URL processing not supported for OpenAI-compatible format. "
            "Please download the file and use process_file() instead."
        )
        return ""

    async def aprocess_file(
        self,
        file_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> str:
        """Async: Process a local file with OCR and return markdown formatted text.

        Uses native async implementation with concurrency for PDF page processing.

        For PDFs: renders pages to images and processes each page in parallel
        For images: processes directly

        Args:
            file_path: Path to the file
            progress_callback: Optional callback for progress updates (PDF only)
                Called with (current_page, total_pages, status, message)

        Returns:
            Extracted text in Markdown format
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

        # Image handling (fallback to sync method)
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""

        # Use async SDK for single image as well
        messages = self._build_request_payload(p)
        if not messages:
            return ""
        try:
            client = self._get_async_client()
            resp = await client.chat.completions.create(
                model=self.config.get_model(), messages=messages
            )
            if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
                return resp.choices[0].message.content
            return ""
        except Exception as e:
            logger.error(f"OpenAI async request failed: {e!s}")
            return ""

    # --------------------
    # PDF processing
    # --------------------
    def _process_pdf(self, pdf_path: Path) -> str:
        """Render PDF pages to images and OCR each page.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Combined text from all pages
        """
        texts: List[str] = []
        try:
            import warnings

            import pdfplumber

            warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

            images_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
            images_dir.mkdir(parents=True, exist_ok=True)

            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    try:
                        # Render page to image
                        to_img = getattr(page, "to_image", None)
                        if not callable(to_img):
                            logger.error(
                                "pdfplumber page.to_image() unavailable; abort PDF OCR"
                            )
                            return ""

                        img_path = images_dir / f"page_{i + 1}.png"
                        img_obj = to_img(resolution=150)
                        save = getattr(img_obj, "save", None)
                        if not callable(save):
                            logger.error(
                                "pdfplumber image object missing save(); abort PDF OCR"
                            )
                            return ""
                        save(str(img_path))

                        # Build request and send
                        payload = self._build_request_payload(img_path)
                        if not payload:
                            logger.warning(f"Failed to build request for page {i + 1}")
                            continue

                        text = self._send_request(payload)
                        if text and text.strip():
                            header = f"## Page {i + 1}\n\n" if page_count > 1 else ""
                            texts.append(header + text.strip())

                    except Exception as e:
                        logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                        continue

        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return ""

        return "\n\n---\n\n".join(texts)

    # --------------------
    # Async PDF processing with concurrency control
    # --------------------
    async def _send_request_async(self, payload: list) -> str:
        """Async request via OpenAI SDK; returns text content."""
        client = self._get_async_client()
        resp = await client.chat.completions.create(
            model=self.config.get_model(), messages=payload
        )
        if resp.choices and resp.choices[0].message and resp.choices[0].message.content:
            return resp.choices[0].message.content
        logger.warning("OpenAI response has no content")
        return ""

    async def _send_request_with_retry(
        self, payload: dict, page_num: int
    ) -> Tuple[int, str]:
        """Send request with retry mechanism.

        Args:
            payload: Request payload dict
            page_num: Page number (for logging and result ordering)

        Returns:
            Tuple of (page_num, extracted_text)
        """
        max_retries = 2  # internal default

        for attempt in range(max_retries + 1):
            try:
                text = await self._send_request_async(payload)
                if attempt > 0:
                    logger.info(f"Page {page_num} succeeded after {attempt} retries")
                return (page_num, text)

            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Page {page_num} failed after {max_retries} retries: {e!s}"
                    )
                    return (page_num, "")

                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(
                    f"Page {page_num} attempt {attempt + 1} failed, "
                    f"retrying in {wait_time}s: {e!s}"
                )
                await asyncio.sleep(wait_time)

        return (page_num, "")

    async def _process_single_page_async(
        self,
        page_num: int,
        img_path: Path,
        semaphore: asyncio.Semaphore,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        total_pages: int = 0,
    ) -> Tuple[int, str]:
        """Process a single page with concurrency control.

        Args:
            page_num: Page number (1-indexed)
            img_path: Path to the page image
            semaphore: Semaphore for concurrency control
            progress_callback: Optional callback for progress updates
            total_pages: Total number of pages (for progress reporting)

        Returns:
            Tuple of (page_num, extracted_text)
        """
        async with semaphore:
            try:
                if progress_callback:
                    progress_callback(
                        page_num, total_pages, "processing",
                        f"Processing page {page_num}/{total_pages}"
                    )

                # Build request payload
                payload = self._build_request_payload(img_path)
                if not payload:
                    logger.warning(f"Failed to build request for page {page_num}")
                    if progress_callback:
                        progress_callback(
                            page_num, total_pages, "failed",
                            f"Failed to build request for page {page_num}"
                        )
                    return (page_num, "")

                # Send request with retry
                page_num_result, text = await self._send_request_with_retry(
                    payload, page_num
                )

                if text and text.strip():
                    if progress_callback:
                        progress_callback(
                            page_num, total_pages, "completed",
                            f"Completed page {page_num}/{total_pages}"
                        )
                    return (page_num_result, text.strip())
                else:
                    if progress_callback:
                        progress_callback(
                            page_num, total_pages, "failed",
                            f"No text extracted from page {page_num}"
                        )
                    return (page_num_result, "")

            except Exception as e:
                logger.error(f"Failed to process page {page_num}: {e!s}")
                if progress_callback:
                    progress_callback(
                        page_num, total_pages, "failed",
                        f"Error processing page {page_num}: {e!s}"
                    )
                return (page_num, "")

    async def _process_pdf_async(
        self,
        pdf_path: Path,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> str:
        """Render PDF pages to images and OCR each page in parallel.

        Args:
            pdf_path: Path to PDF file
            progress_callback: Optional callback function called with
                (current_page, total_pages, status, message)

        Returns:
            Combined text from all pages in original order
        """
        try:
            import warnings
            import pdfplumber

            warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

            images_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
            images_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Render all pages to images (synchronous)
            logger.info(f"Rendering PDF pages to images: {pdf_path}")
            image_paths: List[Tuple[int, Path]] = []

            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
                logger.info(f"Total pages to process: {page_count}")

                for i, page in enumerate(pdf.pages):
                    try:
                        to_img = getattr(page, "to_image", None)
                        if not callable(to_img):
                            logger.error(
                                "pdfplumber page.to_image() unavailable; abort PDF OCR"
                            )
                            return ""

                        img_path = images_dir / f"page_{i + 1}.png"
                        img_obj = to_img(resolution=150)
                        save = getattr(img_obj, "save", None)
                        if not callable(save):
                            logger.error(
                                "pdfplumber image object missing save(); abort PDF OCR"
                            )
                            return ""
                        save(str(img_path))
                        image_paths.append((i + 1, img_path))

                    except Exception as e:
                        logger.warning(f"Failed to render page {i + 1}: {e!s}")
                        continue

            if not image_paths:
                logger.error("No pages were successfully rendered")
                return ""

            # Step 2: Process all pages in parallel with concurrency control
            max_concurrency = 5  # internal default
            semaphore = asyncio.Semaphore(max_concurrency)

            logger.info(
                f"Processing {len(image_paths)} pages with max concurrency: {max_concurrency}"
            )

            tasks = [
                self._process_single_page_async(
                    page_num, img_path, semaphore, progress_callback, page_count
                )
                for page_num, img_path in image_paths
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Step 3: Sort results by page number and combine
            page_texts: List[Tuple[int, str]] = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result!s}")
                    continue
                if isinstance(result, tuple) and len(result) == 2:
                    page_texts.append(result)

            # Sort by page number
            page_texts.sort(key=lambda x: x[0])

            # Combine texts
            texts: List[str] = []
            for page_num, text in page_texts:
                if text:
                    header = f"## Page {page_num}\n\n" if page_count > 1 else ""
                    texts.append(header + text)

            logger.info(
                f"Async PDF processing completed: {len(texts)}/{page_count} pages extracted"
            )
            return "\n\n---\n\n".join(texts)

        except Exception as e:
            logger.error(f"Async PDF processing failed: {e!s}")
            return ""

    # --------------------
    # Abstract requirements (no-op)
    # --------------------
    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        """Not used - response parsing is handled in _send_request()"""
        return "", []

    def save_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Not used - no images extracted from text-only responses"""
        return
