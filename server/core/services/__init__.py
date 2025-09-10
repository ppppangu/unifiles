"""
服务模块
提供高级服务接口
"""

from .embedding_service import (
    EmbeddingProvider, SingletonEmbeddingProvider, 
    BatchEmbeddingProcessor, EmbeddingService,
    get_embedding_service, set_global_embedding_provider
)
from .storage_service import (
    MinIOStorageManager, VectorStorageManager, StorageService,
    get_storage_service
)
from .document_processor import (
    DocumentProcessingService, get_document_processor, mineru_process
)

__all__ = [
    'EmbeddingProvider', 'SingletonEmbeddingProvider', 
    'BatchEmbeddingProcessor', 'EmbeddingService',
    'get_embedding_service', 'set_global_embedding_provider',
    'MinIOStorageManager', 'VectorStorageManager', 'StorageService',
    'get_storage_service',
    'DocumentProcessingService', 'get_document_processor', 'mineru_process'
]