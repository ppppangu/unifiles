"""
核心模块
提供所有核心功能的统一访问点
"""

# 数据库相关
from .database import (
    DatabaseManager,
    UserModel, KnowledgeBaseModel, DocumentModel, FileModel,
    ChunkModel, PhotoModel, ProcessingLogModel,
    FileStatus, ProcessingStage, ProcessingStatus
)

# 流水线相关
from .pipelines import (
    FileFormatValidator, PDFConverter, FormatValidationPipeline,
    OCRProvider, SimplePDFReader, MineruOCRProvider,
    FileDownloader, TextProcessor, PDFProcessingPipeline
)

# 服务相关
from .services import (
    EmbeddingProvider, SingletonEmbeddingProvider, 
    BatchEmbeddingProcessor, EmbeddingService,
    get_embedding_service, set_global_embedding_provider,
    MinIOStorageManager, VectorStorageManager, StorageService,
    get_storage_service,
    DocumentProcessingService, get_document_processor, mineru_process
)

# 工具函数
from .utils.tools import (
    read_config, read_pg_config, read_minio_config,
    mk_need_path, detect_content_type, convert_to_internal_minio_url
)

__version__ = "1.0.0"

__all__ = [
    # 数据库
    'DatabaseManager',
    'UserModel', 'KnowledgeBaseModel', 'DocumentModel', 'FileModel',
    'ChunkModel', 'PhotoModel', 'ProcessingLogModel',
    'FileStatus', 'ProcessingStage', 'ProcessingStatus',
    
    # 流水线
    'FileFormatValidator', 'PDFConverter', 'FormatValidationPipeline',
    'OCRProvider', 'SimplePDFReader', 'MineruOCRProvider',
    'FileDownloader', 'TextProcessor', 'PDFProcessingPipeline',
    
    # 服务
    'EmbeddingProvider', 'SingletonEmbeddingProvider', 
    'BatchEmbeddingProcessor', 'EmbeddingService',
    'get_embedding_service', 'set_global_embedding_provider',
    'MinIOStorageManager', 'VectorStorageManager', 'StorageService',
    'get_storage_service',
    'DocumentProcessingService', 'get_document_processor', 'mineru_process',
    
    # 工具函数
    'read_config', 'read_pg_config', 'read_minio_config',
    'mk_need_path', 'detect_content_type', 'convert_to_internal_minio_url'
]