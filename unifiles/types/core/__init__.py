"""
Core 模块类型定义

包含核心业务逻辑的所有类型。
"""

# Users
from .users import (
    UserModel,
    AccessKeyModel,
)

# Files
from .files import (
    FileModel,
    FileStatus,
    FileProcessingLogModel,
)

# Storage
from .storage import (
    ProviderType,
    ConfigSource,
    BaseConnection,
    LocalConnection,
    MinIOConnection,
    S3Connection,
    AzureConnection,
    GCSConnection,
    ConnectionConfig,
    StorageConfig,
    create_connection_from_dict,
)

# Extraction
from .extraction import (
    ExtractionStatus,
    ExtractedDocumentModel,
    ExtractedAssetModel,
)

# Knowledge Base
from .knowledge import (
    KnowledgeBaseStatus,
    KnowledgeBaseModel,
    DocumentModel,
    KBStatisticsModel,
)

# Components
from .components import (
    ComponentType,
    ComponentModel,
    ChunkModel,
    PhotoModel,
)

__all__ = [
    # Users
    "UserModel",
    "AccessKeyModel",

    # Files
    "FileModel",
    "FileStatus",
    "FileProcessingLogModel",

    # Storage
    "ProviderType",
    "ConfigSource",
    "BaseConnection",
    "LocalConnection",
    "MinIOConnection",
    "S3Connection",
    "AzureConnection",
    "GCSConnection",
    "ConnectionConfig",
    "StorageConfig",
    "create_connection_from_dict",

    # Extraction
    "ExtractionStatus",
    "ExtractedDocumentModel",
    "ExtractedAssetModel",

    # Knowledge
    "KnowledgeBaseStatus",
    "KnowledgeBaseModel",
    "DocumentModel",
    "KBStatisticsModel",

    # Components
    "ComponentType",
    "ComponentModel",
    "ChunkModel",
    "PhotoModel",
]
