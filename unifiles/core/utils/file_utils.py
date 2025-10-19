"""
File utility functions for detecting and handling file types
"""

import mimetypes
from pathlib import Path
from typing import Optional


def detect_content_type(filename: str) -> Optional[str]:
    """
    Detect the content type (MIME type) of a file based on its filename extension.
    
    Args:
        filename: The filename to analyze
        
    Returns:
        The MIME type string, or None if it cannot be determined
    """
    if not filename:
        return None

    # Get the file extension
    file_path = Path(filename)

    # Use mimetypes module to guess the content type
    content_type, _ = mimetypes.guess_type(filename)

    # Handle some common cases that might not be detected properly
    extension = file_path.suffix.lower()

    if content_type is None:
        # Define some common mappings for unsupported extensions
        extension_mappings = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.odt': 'application/vnd.oasis.opendocument.text',
            '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
            '.odp': 'application/vnd.oasis.opendocument.presentation',
            '.ipynb': 'application/json',
            '.md': 'text/markdown',
        }

        content_type = extension_mappings.get(extension)

    return content_type
