"""
核心模块
提供所有核心功能的统一访问点
"""

# 数据库相关
# 工具函数
from .config.env_config import (
    convert_to_internal_minio_url,
    mk_need_path,
    read_config,
    read_minio_config,
    read_pg_config,
)
from .database import (
    ChunkModel,
    DocumentModel,
    FileModel,
    FileProcessingLogModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingStage,
    ProcessingStatus,
    UnifiedDatabaseManager,
    UserModel,
)

# 流水线相关
from .pipelines import (
    FileDownloader,
    FileFormatValidator,
    FormatValidationPipeline,
    MineruOCRProvider,
    OCRProvider,
    PDFConverter,
    PDFProcessingPipeline,
    SimplePDFReader,
    TextProcessor,
)

# 服务相关
from .services import (
    AuthService,
    FileService,
)
from .utils.file_utils import detect_content_type

__version__ = "1.0.0"

__all__ = [
    "AuthService",
    "ChunkModel",
    "DocumentModel",
    "FileDownloader",
    # 流水线
    "FileFormatValidator",
    "FileModel",
    "FileProcessingLogModel",
    # 服务
    "FileService",
    "FileStatus",
    "FormatValidationPipeline",
    "KnowledgeBaseModel",
    "MineruOCRProvider",
    "OCRProvider",
    "PDFConverter",
    "PDFProcessingPipeline",
    "PhotoModel",
    "ProcessingStage",
    "ProcessingStatus",
    "SimplePDFReader",
    "TextProcessor",
    "UnifiedDatabaseManager",
    "UserModel",
    "convert_to_internal_minio_url",
    "detect_content_type",
    "mk_need_path",
    # 工具函数
    "read_config",
    "read_minio_config",
    "read_pg_config",
]
