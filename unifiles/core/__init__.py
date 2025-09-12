"""
核心模块
提供所有核心功能的统一访问点
"""

# 数据库相关
from .database import (
    ChunkModel,
    DatabaseManager,
    DocumentModel,
    FileModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingLogModel,
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
    BatchEmbeddingProcessor,
    DocumentProcessingService,
    EmbeddingProvider,
    EmbeddingService,
    MinIOStorageManager,
    SingletonEmbeddingProvider,
    StorageService,
    VectorStorageManager,
    get_document_processor,
    get_embedding_service,
    get_storage_service,
    mineru_process,
    set_global_embedding_provider,
)

# 工具函数
from .utils.tools import (
    convert_to_internal_minio_url,
    detect_content_type,
    mk_need_path,
    read_config,
    read_minio_config,
    read_pg_config,
)

__version__ = "1.0.0"

__all__ = [
    # 数据库
    "DatabaseManager",
    "UserModel",
    "KnowledgeBaseModel",
    "DocumentModel",
    "FileModel",
    "ChunkModel",
    "PhotoModel",
    "ProcessingLogModel",
    "FileStatus",
    "ProcessingStage",
    "ProcessingStatus",
    # 流水线
    "FileFormatValidator",
    "PDFConverter",
    "FormatValidationPipeline",
    "OCRProvider",
    "SimplePDFReader",
    "MineruOCRProvider",
    "FileDownloader",
    "TextProcessor",
    "PDFProcessingPipeline",
    # 服务
    "EmbeddingProvider",
    "SingletonEmbeddingProvider",
    "BatchEmbeddingProcessor",
    "EmbeddingService",
    "get_embedding_service",
    "set_global_embedding_provider",
    "MinIOStorageManager",
    "VectorStorageManager",
    "StorageService",
    "get_storage_service",
    "DocumentProcessingService",
    "get_document_processor",
    "mineru_process",
    # 工具函数
    "read_config",
    "read_pg_config",
    "read_minio_config",
    "mk_need_path",
    "detect_content_type",
    "convert_to_internal_minio_url",
]
