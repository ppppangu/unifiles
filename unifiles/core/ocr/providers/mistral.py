import asyncio
import base64
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from loguru import logger
from mistralai import Mistral

from ..base import BaseOCRProvider
from ..config.mistral import MistralConfig


class MistralOCRProvider(BaseOCRProvider):
    """Mistral OCR provider implementation"""

    def __init__(self, config: MistralConfig = None):
        if config is None:
            config = MistralConfig()
        super().__init__(config)
        self.client = None

    def get_provider_name(self) -> str:
        """获取提供者名称"""
        return "mistral"

    def _get_client(self) -> Mistral:
        """Get or create Mistral client"""
        if self.client is None:
            self.client = Mistral(api_key=self.config.get_api_key())
        return self.client

    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process a local file with OCR and return markdown formatted text"""
        if not self.config.validate():
            return ""

        file_path = Path(file_path)

        if not self.validate_file(file_path):
            logger.error(f"File validation failed: {file_path}")
            return ""

        logger.info(f"Processing file: {file_path.name}")

        try:
            client = self._get_client()

            # Read and encode file
            with open(file_path, "rb") as file:
                file_data = file.read()
                base64_data = base64.b64encode(file_data).decode("utf-8")

            # Process with OCR
            response = client.ocr.process(
                include_image_base64=True,
                model=self.config.get_model(),
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_data}",
                },
            )

            # Extract text from response
            text, images = self._extract_data_from_response(response)

            # Create images directory based on input file name
            images_dir = file_path.parent / f"{file_path.stem}_images"
            self.save_to_images(images, images_dir)
            self.save_to_markdown(text, file_path.parent / f"{file_path.stem}.md")
            logger.success("OCR processing completed")
            return text

        except Exception as e:
            logger.error(f"Error processing file: {e!s}")
            return ""

    def process_url(self, url: str) -> str:
        """Process a file from URL with OCR and return markdown formatted text"""
        # TODO: Implement URL processing
        raise NotImplementedError("URL processing not yet implemented")

    # --------------------
    # Async counterparts
    # --------------------
    async def aprocess_file(self, file_path: Union[str, Path]) -> str:
        """Async: Process a local file with OCR and return markdown formatted text.

        Uses asyncio.to_thread to offload blocking file I/O and SDK calls.
        """
        if not self.config.validate():
            return ""

        file_path = Path(file_path)

        if not self.validate_file(file_path):
            logger.error(f"File validation failed: {file_path}")
            return ""

        logger.info(f"[async] Processing file: {file_path.name}")

        try:
            client = self._get_client()

            # Read and encode file in a thread
            def _read_b64(p: Path) -> str:
                with open(p, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")

            base64_data = await asyncio.to_thread(_read_b64, file_path)

            # Use SDK native async API
            response = await client.ocr.process_async(
                include_image_base64=True,
                model=self.config.get_model(),
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_data}",
                },
            )

            # Extract and persist
            text, images = self._extract_data_from_response(response)
            # Create images directory based on input file name
            images_dir = file_path.parent / f"{file_path.stem}_images"
            await asyncio.gather(
                self.asave_to_images(images, images_dir),
                self.asave_to_markdown(text, file_path.parent / f"{file_path.stem}.md"),
            )
            logger.success("[async] OCR processing completed")
            return text

        except Exception as e:
            logger.error(f"Error processing file (async): {e!s}")
            return ""

    async def aprocess_url(self, url: str) -> str:
        """Async: Process a file from URL with OCR and return markdown formatted text."""
        raise NotImplementedError("URL processing not yet implemented")

    # --------------------
    # OCRProvider Protocol Implementation
    # --------------------

    async def extract_markdown_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取Markdown格式文本 - 实现OCRProvider协议"""
        # 占位符实现
        return "Markdown content from PDF"

    async def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        """从PDF提取文本 - 实现OCRProvider协议"""
        # 占位符实现
        return "Text content from PDF"

    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        """Extract markdown text and images from Mistral OCR API response"""
        if not hasattr(response, "pages") or not response.pages:
            logger.error("No pages found in OCR response")
            return "", []

        # Combine all pages' markdown content
        pages_text = []
        images = []
        for i, page in enumerate(response.pages):
            if hasattr(page, "images") and page.images:
                images.extend(page.images)

            if hasattr(page, "markdown") and page.markdown:
                # Add page number for multi-page documents
                if len(response.pages) > 1:
                    pages_text.append(f"## Page {i + 1}\n\n{page.markdown}")
                else:
                    pages_text.append(page.markdown)

        if not pages_text:
            logger.error("No markdown content found in OCR response")
            return "", []

        markdown_text = "\n\n---\n\n".join(pages_text)  # Separate pages with dividers

        return markdown_text, images

    def save_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Save base64 encoded images from Mistral response to files

        Args:
            images: List of image objects from Mistral response
            output_dir: Directory to save images to. If None, saves to current directory.
        """
        if output_dir is None:
            output_dir = Path()
        else:
            output_dir = Path(output_dir)
            # Create directory if it doesn't exist
            output_dir.mkdir(parents=True, exist_ok=True)

        for i, image in enumerate(images):
            try:
                image_base64data = image.image_base64.split(",")[1]
                img_data = base64.b64decode(image_base64data)
                img_path = output_dir / f"img-{i}.jpeg"
                with open(img_path, "wb") as img_file:
                    img_file.write(img_data)
                logger.success(f"Image saved to: {img_path}")
            except Exception as e:
                logger.error(f"Error saving image {i}: {e!s}")
