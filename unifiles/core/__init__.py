"""
核心模块
提供所有核心功能的统一访问点
"""

# 工具函数
from .utils import mk_need_path
from .database import (
    ChunkModel,
    DatabaseManager,
    DocumentModel,
    FileModel,
    FileProcessingLogModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingStage,
    ProcessingStatus,
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
    # 数据库
    "DatabaseManager",
    "ChunkModel",
    "DocumentModel",
    "FileModel",
    "FileProcessingLogModel",
    "FileStatus",
    "KnowledgeBaseModel",
    "PhotoModel",
    "ProcessingStage",
    "ProcessingStatus",
    "UserModel",
    # 流水线
    "FileDownloader",
    "FileFormatValidator",
    "FormatValidationPipeline",
    "MineruOCRProvider",
    "OCRProvider",
    "PDFConverter",
    "PDFProcessingPipeline",
    "SimplePDFReader",
    "TextProcessor",
    # 服务
    "AuthService",
    "FileService",
    # 工具函数
    "detect_content_type",
    "mk_need_path",
]
