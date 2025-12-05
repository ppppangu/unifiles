import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union

try:
    from typing import TypedDict
except ImportError:  # pragma: no cover - for very old Python versions
    from typing_extensions import TypedDict

if TYPE_CHECKING:
    from .config.base import BaseConfig


class OCRImageInfo(TypedDict, total=False):
    """Standard image metadata returned by OCR providers.

    Providers that return page-level image information should populate:
    - filename: Image filename (without any storage prefix)
    - page: Page number (0-indexed)
    - index: Image index on the page
    - extension: File extension (e.g. 'png', 'jpeg')
    - size_bytes: Image size in bytes

    Optional fields allow different providers/pipelines to cooperate:
    - bytes: Raw image bytes (preferred for uploads, avoids temp files)
    - path: Local file path (legacy/simple mode fallback)
    - object_path: Storage object path (filled by storage pipeline)
    - public_url: Public access URL (filled by storage pipeline)
    """

    filename: str
    page: int
    index: int
    extension: str
    size_bytes: int
    bytes: bytes
    path: str
    object_path: str
    public_url: str


OCROutput = Tuple[str, List[OCRImageInfo]]


class BaseOCRProvider(ABC):
    """Base OCR provider class that defines the interface for all OCR providers."""

    def __init__(self, config: "BaseConfig"):
        self.config = config

    @abstractmethod
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process a local file with OCR and return markdown formatted text."""
        ...

    @abstractmethod
    def process_url(self, url: str) -> str:
        """Process a file from URL with OCR and return markdown formatted text."""
        ...

    def validate_file(self, file_path: Union[str, Path]) -> bool:
        """Common file validation logic."""
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        # Check file size (10MB limit)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        return not file_size_mb > 10

    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        """Extract markdown text and images from OCR API response.

        Subclasses must implement this if they rely on the synchronous
        `process_file` helper that parses provider-specific responses.
        """
        raise NotImplementedError(
            "Subclasses must implement _extract_data_from_response"
        )

    def save_to_markdown(
        self, text: str, output_path: Union[str, Path], title: Optional[str] = None
    ) -> None:
        """Save extracted text to a markdown file."""
        output_path = Path(output_path)

        content = text
        if title:
            content = f"# {title}\n\n{text}"

        output_path.write_text(content, encoding="utf-8")

    def save_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Save images to files - to be implemented by subclasses based on their response format.

        Args:
            images: List of image objects to save
            output_dir: Directory to save images to. If None, saves to current directory.
        """
        raise NotImplementedError("Subclasses must implement save_to_images")

    # --------------------
    # Async counterparts
    # --------------------
    async def aprocess_file(self, file_path: Union[str, Path], **kwargs) -> OCROutput:
        """Async wrapper for `process_file` using the standard OCROutput contract.

        Args:
            file_path: Path to the file to process
            **kwargs: Additional arguments (subclasses may accept output_dir, etc.)

        Returns:
            OCROutput: (markdown_text, images_info)
                - markdown_text: Extracted text in markdown format
                - images_info: List of :class:`OCRImageInfo` metadata dictionaries.

        Notes:
            - Default implementation offloads the synchronous `process_file` to a
              worker thread and wraps its return value into OCROutput.
            - For providers that override `process_file` to return OCROutput
              directly, the result will be passed through unchanged.
            - Subclasses should override this method if they provide a native
              async implementation or need additional parameters.
        """
        result = await asyncio.to_thread(self.process_file, file_path)
        # For backward compatibility: if subclass returns only str, wrap it
        if isinstance(result, str):
            return result, []
        return result

    async def aprocess_url(self, url: str) -> str:
        """Async wrapper for process_url using a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(self.process_url, url)

    async def asave_to_markdown(
        self, text: str, output_path: Union[str, Path], title: Optional[str] = None
    ) -> None:
        """Async wrapper for save_to_markdown."""
        await asyncio.to_thread(self.save_to_markdown, text, output_path, title)

    async def asave_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Async wrapper for save_to_images."""
        await asyncio.to_thread(self.save_to_images, images, output_dir)
