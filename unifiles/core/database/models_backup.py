"""
DEPRECATED: This module is kept for backward compatibility only.
Please use unifiles.types instead.

All types have been moved to the new types/ structure:
- from unifiles.types import FileModel, FileStatus, UserModel, etc.
- from unifiles.types.core import ChunkModel, PhotoModel, etc.

Old structure (DEPRECATED):
  core/database/models.py

New structure (RECOMMENDED):
  types/
    __init__.py          # Top-level exports (80% use case)
    shared.py            # Shared types
    core/
      users.py           # User system types
      files.py           # File management types
      storage.py         # Storage system types
      extraction.py      # Content extraction types
      knowledge.py       # Knowledge base types
      components.py      # Component system types
"""

# Re-export all types from new location for backward compatibility
from unifiles.types import (
    FileModel,
    FileStatus,
    UserModel,
    ProcessingStatus,
    ProcessingStage,
    KnowledgeBaseModel,
    DocumentModel,
    ExtractedDocumentModel,
    AccessKeyModel,
    FileProcessingLogModel,
    KnowledgeBaseStatus,
    ExtractionStatus,
)
from unifiles.types.core import (
    ChunkModel,
    PhotoModel,
    ComponentModel,
    ComponentType,
    ExtractedAssetModel,
    KBStatisticsModel,
)

# Legacy alias - StorageType is now ProviderType
from unifiles.types.core.storage import ProviderType
StorageType = ProviderType

# Legacy model - StorageConfigModel is now just StorageConfig
from unifiles.types import StorageConfig as StorageConfigModel

__all__ = [
    # Enums
    "FileStatus",
    "ProcessingStage",
    "ProcessingStatus",
    "StorageType",
    "ExtractionStatus",
    "KnowledgeBaseStatus",
    "ComponentType",
    # Models
    "UserModel",
    "AccessKeyModel",
    "StorageConfigModel",
    "FileModel",
    "FileProcessingLogModel",
    "ExtractedDocumentModel",
    "ExtractedAssetModel",
    "KnowledgeBaseModel",
    "DocumentModel",
    "KBStatisticsModel",
    "ComponentModel",
    "ChunkModel",
    "PhotoModel",
]
