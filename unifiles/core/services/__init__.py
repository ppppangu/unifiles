"""
服务模块
提供高级服务接口
"""

from .document_processor import (
    DocumentProcessingService,
    get_document_processor,
    mineru_process,
)
from .embedding_service import (
    BatchEmbeddingProcessor,
    EmbeddingProvider,
    EmbeddingService,
    SingletonEmbeddingProvider,
    get_embedding_service,
    set_global_embedding_provider,
)
from .storage_service import (
    MinIOStorageManager,
    StorageService,
    VectorStorageManager,
    get_storage_service,
)

__all__ = [
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
]
