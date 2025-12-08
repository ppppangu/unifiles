import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Union

import fitz  # PyMuPDF
import pdfplumber
from loguru import logger

from ..base import BaseOCRProvider, OCROutput, OCRImageInfo
from ..config.simple import SimpleOCRConfig


class SimpleOCRProvider(BaseOCRProvider):
    """Lightweight PDF extractor using pdfplumber (text) + PyMuPDF (images).

    Keeps the interface consistent with other OCR providers so the factory and
    pipelines no longer need to special-case the `simple` mode.
    """

    def __init__(self, config: SimpleOCRConfig | None = None):
        super().__init__(config or SimpleOCRConfig())

    def get_provider_name(self) -> str:
        return "simple"

    # --------------------
    # Sync APIs
    # --------------------
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Synchronous extraction; returns markdown text only."""
        if not self.config.validate():
            return ""

        path = Path(file_path)
        if not path.exists():
            logger.error(f"[Simple OCR] File not found: {path}")
            return ""

        text, _ = self._extract_text_and_images(path)
        return text

    def process_url(self, url: str) -> str:
        """URL handling is not supported in the simple provider."""
        logger.warning("[Simple OCR] URL processing is not supported")
        return ""

    # --------------------
    # Async APIs
    # --------------------
    async def aprocess_file(
        self, file_path: Union[str, Path], **kwargs
    ) -> OCROutput:
        """Async extraction; returns markdown text and image metadata."""
        if not self.config.validate():
            return "", []

        path = Path(file_path)
        if not path.exists():
            logger.error(f"[Simple OCR] File not found: {path}")
            return "", []

        return await asyncio.to_thread(self._extract_text_and_images, path)

    # --------------------
    # Internal helpers
    # --------------------
    def _extract_text_and_images(self, path: Path) -> OCROutput:
        """Extract text and images with markdown image references inline."""
        images = self._extract_images(path)
        images_by_page: Dict[int, List[OCRImageInfo]] = defaultdict(list)
        for img in images:
            images_by_page[img["page"]].append(img)

        markdown_parts: List[str] = []

        try:
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)
                logger.info(
                    f"[Simple OCR] Starting extraction: {path.name}, pages={page_count}"
                )
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        markdown_parts.append(f"{page_text}\n\n")

                    # Keep image references adjacent to their page text
                    if page_num in images_by_page:
                        for img in images_by_page[page_num]:
                            markdown_parts.append(
                                f"![{img['filename']}]({img['filename']})\n\n"
                            )
        except Exception as e:
            logger.error(f"[Simple OCR] Failed to read PDF text: {e}")

        markdown_text = "".join(markdown_parts).strip()
        if not markdown_text:
            markdown_text = (
                "# PDF Content\n\n这是一个占位符，用于保证边缘情况，"
                "需要图片处理请使用OCR提供商模式"
            )
            logger.info(
                "[Simple OCR] No text extracted, using placeholder content for empty PDF"
            )

        logger.info(
            "[Simple OCR] Extraction completed: chars=%d, images=%d",
            len(markdown_text),
            len(images),
        )
        return markdown_text, images

    def _extract_images(self, path: Path) -> List[OCRImageInfo]:
        """Extract images as in-memory bytes with metadata."""
        images: List[OCRImageInfo] = []
        try:
            doc = fitz.open(path)
            for page_num, page in enumerate(doc):
                image_list = page.get_images(full=True)
                for idx, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        extension = base_image["ext"]
                        filename = f"page_{page_num:03d}_img_{idx:03d}.{extension}"

                        images.append(
                            {
                                "page": page_num,
                                "index": idx,
                                "filename": filename,
                                "bytes": image_bytes,
                                "extension": extension,
                                "size_bytes": len(image_bytes),
                            }
                        )
                    except Exception as image_err:
                        logger.warning(
                            f"[Simple OCR] Failed to extract image on page {page_num}: {image_err}"
                        )
                        continue
        except Exception as e:
            logger.error(f"[Simple OCR] Failed to extract images: {e}")

        return images
