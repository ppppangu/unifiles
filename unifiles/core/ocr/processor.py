import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Union

from .factory import OCRProviderFactory
from .base import BaseOCRProvider


class OCRProcessor:
    """Main OCR processor that provides a unified interface for all OCR providers"""
    
    def __init__(self, provider_name: str = 'mistral', config=None):
        """Initialize OCR processor with specified provider
        
        Args:
            provider_name: Name of the OCR provider to use
            config: Optional configuration for the provider
        """
        self.provider_name = provider_name
        self.provider: BaseOCRProvider = OCRProviderFactory.create_provider(provider_name, config)
    
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process a local file with OCR and return markdown formatted text
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            str: Extracted text in markdown format
        """
        return self.provider.process_file(file_path)
    
    def process_url(self, url: str) -> str:
        """Process a file from URL with OCR and return markdown formatted text
        
        Args:
            url: URL of the file to process
            
        Returns:
            str: Extracted text in markdown format
        """
        return self.provider.process_url(url)
    
    def process_directory(self, directory_path: Union[str, Path], 
                         file_extensions: list = None) -> dict:
        """Process all files in a directory
        
        Args:
            directory_path: Path to the directory containing files
            file_extensions: List of file extensions to process (e.g., ['.pdf', '.png'])
            
        Returns:
            dict: Dictionary mapping file paths to extracted text
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists() or not directory_path.is_dir():
            return {}
        
        if file_extensions is None:
            file_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.avif', '.pptx', '.docx']
        
        results = {}
        for file_path in directory_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in file_extensions:
                text = self.process_file(file_path)
                if text:
                    results[str(file_path)] = text
        
        return results
    
    def get_supported_providers(self) -> list:
        """Get list of supported OCR providers"""
        return OCRProviderFactory.get_supported_providers()
    
    def switch_provider(self, provider_name: str, config=None):
        """Switch to a different OCR provider
        
        Args:
            provider_name: Name of the new provider
            config: Optional configuration for the new provider
        """
        self.provider_name = provider_name
        self.provider = OCRProviderFactory.create_provider(provider_name, config)

    # --------------------
    # Async counterparts
    # --------------------
    async def aprocess_file(self, file_path: Union[str, Path]) -> str:
        """Async: Process a local file with OCR and return markdown formatted text."""
        return await self.provider.aprocess_file(file_path)

    async def aprocess_url(self, url: str) -> str:
        """Async: Process a file from URL with OCR and return markdown formatted text."""
        return await self.provider.aprocess_url(url)

    async def aprocess_directory(
        self,
        directory_path: Union[str, Path],
        file_extensions: List[str] | None = None,
        concurrency: int = 5,
    ) -> Dict[str, str]:
        """Async: Process all files in a directory concurrently.

        Args:
            directory_path: Path to the directory containing files
            file_extensions: List of file extensions to process (e.g., ['.pdf', '.png'])
            concurrency: Max number of concurrent OCR jobs

        Returns:
            dict: Mapping file path -> extracted text
        """
        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            return {}

        if file_extensions is None:
            file_extensions = [
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".avif",
                ".pptx",
                ".docx",
            ]

        # Prepare tasks
        files: List[Path] = [
            p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in file_extensions
        ]
        if not files:
            return {}

        sem = asyncio.Semaphore(max(1, concurrency))

        async def worker(p: Path) -> Tuple[str, str]:
            async with sem:
                text = await self.aprocess_file(p)
                return str(p), text

        results: Dict[str, str] = {}
        tasks = [asyncio.create_task(worker(p)) for p in files]
        for coro in asyncio.as_completed(tasks):
            path, text = await coro
            if text:
                results[path] = text
        return results
