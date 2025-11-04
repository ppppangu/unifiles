"""
Unifiles 类型定义

按功能领域组织，遵循 FastAPI 风格。

使用示例:
    # 最常用的类型（80%场景）
    from unifiles.types import (
        FileModel,
        FileStatus,
        UserModel,
        ProviderType,
        StorageConfig,
    )

    # 特定领域类型（15%场景）
    from unifiles.types.core import (
        ExtractedDocumentModel,
        KnowledgeBaseModel,
        ComponentModel,
    )

    # 少用的类型（5%场景）
    from unifiles.types.core.extraction import ExtractedAssetModel
"""

# ===== 最常用的类型（导出到顶层）=====

# 用户系统
from .core.users import (
    UserModel,
    AccessKeyModel,
)

# 文件管理
from .core.files import (
    FileModel,
    FileStatus,
    FileProcessingLogModel,
)

# 存储系统
from .core.storage import (
    ProviderType,
    ConfigSource,
    StorageConfig,
    BaseConnection,
    LocalConnection,
    MinIOConnection,
    S3Connection,
    AzureConnection,
    GCSConnection,
    ConnectionConfig,
    create_connection_from_dict,
)

# 处理流程
from .shared import (
    ProcessingStatus,
    ProcessingStage,
)

# 知识库（常用）
from .core.knowledge import (
    KnowledgeBaseModel,
    DocumentModel,
    KnowledgeBaseStatus,
)

# 提取（常用）
from .core.extraction import (
    ExtractedDocumentModel,
    ExtractionStatus,
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
    "StorageConfig",
    "BaseConnection",
    "LocalConnection",
    "MinIOConnection",
    "S3Connection",
    "AzureConnection",
    "GCSConnection",
    "ConnectionConfig",
    "create_connection_from_dict",

    # Processing
    "ProcessingStatus",
    "ProcessingStage",

    # Knowledge Base
    "KnowledgeBaseModel",
    "DocumentModel",
    "KnowledgeBaseStatus",

    # Extraction
    "ExtractedDocumentModel",
    "ExtractionStatus",
]
