"""
Utils package for file server.
"""

__version__ = "0.1.0"

# Re-export selected APIs from submodules
from .file_upload_utils import (
    DOCUMENT_FILE_TYPES,
    PDF_FILE_TYPES,
    SUPPORTED_FILE_TYPES,
    create_minio_client,
    ensure_bucket_exists,
    generate_object_path,
    generate_public_url,
    get_supported_file_types,
    upload_file_to_minio,
    upload_file_with_validation,
    validate_file_content,
    validate_file_type,
)

# Control what `from utils import *` exposes
__all__ = [
    "DOCUMENT_FILE_TYPES",
    "PDF_FILE_TYPES",
    "SUPPORTED_FILE_TYPES",
    "validate_file_type",
    "validate_file_content",
    "create_minio_client",
    "ensure_bucket_exists",
    "generate_object_path",
    "generate_public_url",
    "upload_file_to_minio",
    "upload_file_with_validation",
    "get_supported_file_types",
]
