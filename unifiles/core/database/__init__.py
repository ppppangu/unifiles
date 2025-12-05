# New unified managers (recommended)
from .async_task_manager import AsyncTaskManager, async_task_manager
from .connection import (
    DatabaseConnectionPool,
    close_connection_pool,
    get_connection_pool,
    initialize_connection_pool,
)

# Legacy managers (deprecated, for backward compatibility)
from .deprecated.base import DatabaseManager as LegacyDatabaseManager
from .deprecated.base import FileDBManager as LegacyFileDBManager
from .deprecated.base import file_db_manager as legacy_file_db_manager
from .deprecated.manager import DatabaseManager as LegacyFullDatabaseManager
from .deprecated.secure_manager import SecureFileDBManager as LegacySecureFileDBManager
from .deprecated.secure_manager import (
    secure_file_db_manager as legacy_secure_file_db_manager,
)
from .extraction_manager import ExtractionDBManager as UnifiedExtractionDBManager
from .extraction_manager import extraction_db_manager
from .file_manager import FileDBManager as UnifiedFileDBManager
from .file_manager import unified_file_db_manager
from .knowledge_base_manager import (
    KnowledgeBaseDBManager as UnifiedKnowledgeBaseDBManager,
)
from .knowledge_base_manager import unified_kb_db_manager

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
from .user_manager import UserDBManager as UnifiedUserDBManager
from .user_manager import unified_user_db_manager

# Validation utilities
from .validation import (
    validate_database_connection,
    validate_storage_connection,
    validate_user_id,
    validate_user_id_in_minio,
)

# Backward compatibility aliases (point to new unified managers)
DatabaseManager = LegacyFullDatabaseManager  # For knowledge_bases.py
FileDBManager = UnifiedFileDBManager  # Use new unified manager
file_db_manager = unified_file_db_manager  # Use new unified manager
SecureFileDBManager = (
    UnifiedFileDBManager  # Use new unified manager (has all security features)
)
secure_file_db_manager = unified_file_db_manager  # Use new unified manager

__all__ = [
    # New unified managers (RECOMMENDED)
    "UnifiedDatabaseManager",
    "unified_db_manager",
    "UnifiedFileDBManager",
    "unified_file_db_manager",
    "UnifiedKnowledgeBaseDBManager",
    "unified_kb_db_manager",
    "UnifiedUserDBManager",
    "unified_user_db_manager",
    "UnifiedExtractionDBManager",
    "extraction_db_manager",
    "AsyncTaskManager",
    "async_task_manager",
    # Connection pool
    "DatabaseConnectionPool",
    "get_connection_pool",
    "initialize_connection_pool",
    "close_connection_pool",
    # Backward compatibility (DEPRECATED)
    "DatabaseManager",
    "FileDBManager",
    "SecureFileDBManager",
    "file_db_manager",
    "secure_file_db_manager",
    "LegacyDatabaseManager",
    "LegacyFileDBManager",
    "LegacySecureFileDBManager",
    "LegacyFullDatabaseManager",
    "legacy_file_db_manager",
    "legacy_secure_file_db_manager",
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
]
