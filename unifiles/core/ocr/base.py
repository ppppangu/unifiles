import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Tuple, Union

if TYPE_CHECKING:
    from .config.base import BaseConfig


class BaseOCRProvider(ABC):
    """Base OCR provider class that defines the interface for all OCR providers"""

    def __init__(self, config: "BaseConfig"):
        self.config = config

    @abstractmethod
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process a local file with OCR and return markdown formatted text"""
        pass

    @abstractmethod
    def process_url(self, url: str) -> str:
        """Process a file from URL with OCR and return markdown formatted text"""
        pass

    def validate_file(self, file_path: Union[str, Path]) -> bool:
        """Common file validation logic"""
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        # Check file size (10MB limit)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 10:
            return False

        return True

    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        """Extract markdown text and images from OCR API response - to be implemented by subclasses"""
        raise NotImplementedError(
            "Subclasses must implement _extract_data_from_response"
        )

    def save_to_markdown(
        self, text: str, output_path: Union[str, Path], title: str = None
    ) -> None:
        """Save extracted text to a markdown file"""
        output_path = Path(output_path)

        content = text
        if title:
            content = f"# {title}\n\n{text}"

        output_path.write_text(content, encoding="utf-8")

    def save_to_images(self, images: List[Any], output_dir: Union[str, Path] = None) -> None:
        """Save images to files - to be implemented by subclasses based on their response format
        
        Args:
            images: List of image objects to save
            output_dir: Directory to save images to. If None, saves to current directory.
        """
        raise NotImplementedError("Subclasses must implement save_to_images")

    # --------------------
    # Async counterparts
    # --------------------
    async def aprocess_file(self, file_path: Union[str, Path]) -> str:
        """Async wrapper for process_file using a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(self.process_file, file_path)

    async def aprocess_url(self, url: str) -> str:
        """Async wrapper for process_url using a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(self.process_url, url)

    async def asave_to_markdown(
        self, text: str, output_path: Union[str, Path], title: str = None
    ) -> None:
        """Async wrapper for save_to_markdown."""
        await asyncio.to_thread(self.save_to_markdown, text, output_path, title)

    async def asave_to_images(self, images: List[Any], output_dir: Union[str, Path] = None) -> None:
        """Async wrapper for save_to_images."""
        await asyncio.to_thread(self.save_to_images, images, output_dir)
