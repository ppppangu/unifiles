"""
数据库模块
提供数据库管理器、模型和连接池
"""

# Connection pool
# Managers
from .async_task_manager import AsyncTaskManager, async_task_manager
from .connection import (
    DatabaseConnectionPool,
    close_connection_pool,
    get_connection_pool,
    initialize_connection_pool,
)
from .extraction_manager import ExtractionDBManager, extraction_db_manager
from .file_manager import FileDBManager, unified_file_db_manager

# Helpers
from .helpers import (
    parse_db_result_count,
    parse_json_field,
    parse_string_list,
    safe_int,
    to_json_string,
)
from .knowledge_base_manager import KnowledgeBaseDBManager, unified_kb_db_manager

# Models
from .models import (
    ChunkModel,
    ComponentModel,
    DocumentModel,
    ExtractedAssetModel,
    ExtractedDocumentModel,
    FileModel,
    FileProcessingLogModel,
    FileStatus,
    KnowledgeBaseModel,
    PhotoModel,
    ProcessingStage,
    ProcessingStatus,
    UserModel,
)
from .unified_manager import UnifiedDatabaseManager, unified_db_manager
from .user_manager import UserDBManager, unified_user_db_manager

# Validation utilities
from .validation import (
    validate_database_connection,
    validate_storage_connection,
    validate_user_id,
    validate_user_id_in_minio,
)

__all__ = [
    # Connection pool
    "DatabaseConnectionPool",
    "get_connection_pool",
    "initialize_connection_pool",
    "close_connection_pool",
    # Managers
    "UnifiedDatabaseManager",
    "unified_db_manager",
    "FileDBManager",
    "unified_file_db_manager",
    "KnowledgeBaseDBManager",
    "unified_kb_db_manager",
    "UserDBManager",
    "unified_user_db_manager",
    "ExtractionDBManager",
    "extraction_db_manager",
    "AsyncTaskManager",
    "async_task_manager",
    # Models
    "ChunkModel",
    "ComponentModel",
    "DocumentModel",
    "ExtractedAssetModel",
    "ExtractedDocumentModel",
    "FileModel",
    "FileProcessingLogModel",
    "FileStatus",
    "KnowledgeBaseModel",
    "PhotoModel",
    "ProcessingStage",
    "ProcessingStatus",
    "UserModel",
    # Validation
    "validate_database_connection",
    "validate_storage_connection",
    "validate_user_id",
    "validate_user_id_in_minio",
    # Helpers
    "parse_db_result_count",
    "parse_json_field",
    "parse_string_list",
    "safe_int",
    "to_json_string",
]
