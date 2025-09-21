"""
数据库模型定义
提供标准化的数据库操作模型和类型定义
基于新的分层架构设计：文件层 -> 内容提取层 -> 知识库层 -> 组件抽象层 -> 组件子类层
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ================================
# 枚举定义 (Enums)
# ================================


class FileStatus(Enum):
    """文件状态枚举"""

    UPLOADED = "uploaded"
    VALIDATING = "validating"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"
    DELETED = "deleted"


class ProcessingStage(Enum):
    """处理阶段枚举"""

    UPLOAD = "upload"
    VALIDATION = "validation"
    OCR_EXTRACTION = "ocr_extraction"
    MARKDOWN_GENERATION = "markdown_generation"


class ProcessingStatus(Enum):
    """处理状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StorageType(Enum):
    """存储类型枚举"""

    LOCAL = "local"
    OBJECT_STORAGE = "object_storage"


class ExtractionStatus(Enum):
    """提取状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class KnowledgeBaseStatus(Enum):
    """知识库状态枚举"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ComponentType(Enum):
    """组件类型枚举"""

    CHUNK = "chunk"
    PHOTO = "photo"


# ================================
# 用户和权限层 (User & Permission Layer)
# ================================


@dataclass
class UserModel:
    """用户模型"""

    id: str
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    user_status: str = "active"
    user_role: str = "user"
    knowledge_ids: List[str] = field(default_factory=list)
    user_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    def __post_init__(self):
        pass


@dataclass
class AccessKeyModel:
    """访问密钥模型"""

    id: str
    user_id: str
    access_key: str
    name: str
    scopes: List[str] = field(default_factory=lambda: ["read", "write"])
    is_active: bool = True
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    def __post_init__(self):
        pass


# ================================
# 文件管理层 (File Management Layer)
# ================================


@dataclass
class StorageConfigModel:
    """存储配置模型"""

    id: str
    storage_type: StorageType
    storage_name: str
    endpoint: Optional[str] = None
    bucket_name: Optional[str] = None
    region: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    base_path: str = ""
    public_url_prefix: Optional[str] = None
    is_active: bool = True
    config_source: str = "manual"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class FileModel:
    """文件模型 - 文件管理层"""

    id: str
    user_id: str
    filename: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_extension: Optional[str] = None
    bytes: int = 0
    file_size_readable: Optional[str] = None
    file_hash: Optional[str] = None
    hash_algorithm: str = "sha256"
    storage_config_id: Optional[str] = None
    storage_path: str = ""
    status: FileStatus = FileStatus.UPLOADED
    upload_source: str = "web"
    is_deleted: bool = False
    file_category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_config: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
        if self.processing_config is None:
            self.processing_config = {}


@dataclass
class FileProcessingLogModel:
    """文件处理日志模型"""

    id: str
    file_id: str
    stage: ProcessingStage
    status: ProcessingStatus
    message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.error_details is None:
            self.error_details = {}


# ================================
# 内容提取层 (Content Extraction Layer)
# ================================


@dataclass
class ExtractedDocumentModel:
    """提取文档模型 - 内容提取层"""

    id: str
    file_id: str
    user_id: str
    extraction_method: str
    extraction_version: Optional[str] = None
    extraction_engine: Optional[str] = None
    full_markdown: str = ""
    structured_content: Optional[Dict[str, Any]] = None
    document_structure: Optional[Dict[str, Any]] = None
    page_structure: Optional[Dict[str, Any]] = None
    total_pages: int = 0
    total_chars: int = 0
    total_words: int = 0
    total_paragraphs: int = 0
    total_assets: int = 0
    text_blocks_count: int = 0
    image_blocks_count: int = 0
    extraction_status: ExtractionStatus = ExtractionStatus.COMPLETED
    extraction_metadata: Optional[Dict[str, Any]] = None
    processing_config: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    extraction_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.structured_content is None:
            self.structured_content = {}
        if self.document_structure is None:
            self.document_structure = {}
        if self.page_structure is None:
            self.page_structure = {}
        if self.extraction_metadata is None:
            self.extraction_metadata = {}
        if self.processing_config is None:
            self.processing_config = {}
        if self.performance_metrics is None:
            self.performance_metrics = {}


@dataclass
class ExtractedAssetModel:
    """提取资源模型 - 内容提取层"""

    id: str
    extracted_document_id: str
    asset_type: str
    asset_subtype: Optional[str] = None
    asset_name: Optional[str] = None
    original_filename: Optional[str] = None
    storage_config_id: Optional[str] = None
    storage_path: str = ""
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    format: Optional[str] = None
    mime_type: Optional[str] = None
    position_in_document: Optional[int] = None
    asset_description: Optional[str] = None
    extracted_text: Optional[str] = None
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    extraction_confidence: Optional[float] = None
    processing_status: str = "extracted"
    validation_status: str = "pending"
    asset_metadata: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    access_count: int = 0
    reference_count: int = 0
    created_at: Optional[datetime] = None
    extracted_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.asset_metadata is None:
            self.asset_metadata = {}
        if self.extraction_metadata is None:
            self.extraction_metadata = {}


# ================================
# 知识库层 (Knowledge Base Layer)
# ================================


@dataclass
class KnowledgeBaseModel:
    """知识库模型 - 知识库层"""

    id: str
    user_id: str
    name: str
    display_name: Optional[str] = None
    description: str = ""
    kb_type: str = "general"
    kb_category: Optional[str] = None
    visibility: str = "private"
    access_level: str = "owner_only"
    default_chunking_strategy: Optional[Dict[str, Any]] = None
    vector_config: Optional[Dict[str, Any]] = None
    search_config: Optional[Dict[str, Any]] = None
    document_count: int = 0
    component_count: int = 0
    chunk_count: int = 0
    photo_count: int = 0
    total_size_bytes: int = 0
    document_ids: List[str] = field(default_factory=list)
    parent_kb_id: Optional[str] = None
    hierarchy_path: str = "root"
    hierarchy_level: int = 0
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.ACTIVE
    processing_status: str = "ready"
    last_updated_by: Optional[str] = None
    kb_metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_document_added_at: Optional[datetime] = None
    last_processed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.default_chunking_strategy is None:
            self.default_chunking_strategy = {
                "strategy_type": "markdown_hierarchical",
                "max_chunk_size": 1000,
                "overlap_size": 100,
                "preserve_structure": True,
                "split_on_headers": True,
                "min_chunk_size": 50,
                "chunk_overlap_strategy": "sentence_boundary",
            }
        if self.vector_config is None:
            self.vector_config = {
                "embedding_model": "text-embedding-3-small",
                "embedding_dimensions": 1536,
                "similarity_threshold": 0.7,
                "search_strategy": "hybrid",
            }
        if self.search_config is None:
            self.search_config = {
                "enable_semantic_search": True,
                "enable_keyword_search": True,
                "enable_hybrid_search": True,
                "rerank_enabled": False,
                "max_results": 20,
            }
        if self.document_ids is None:
            self.document_ids = []
        if self.kb_metadata is None:
            self.kb_metadata = {}
        if self.tags is None:
            self.tags = []


@dataclass
class DocumentModel:
    """知识库文档模型 - 知识库层"""

    id: str
    knowledge_base_id: str
    extracted_document_id: str
    title: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    document_category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    chunking_strategy: Optional[Dict[str, Any]] = None
    custom_config: Optional[Dict[str, Any]] = None
    processing_status: str = "pending"
    indexing_status: str = "pending"
    validation_status: str = "pending"
    component_count: int = 0
    chunk_count: int = 0
    photo_count: int = 0
    total_chars: int = 0
    total_tokens: int = 0
    document_permissions: Optional[Dict[str, Any]] = None
    access_level: str = "inherited"
    hierarchy_path: str = "root"
    parent_document_id: Optional[str] = None
    document_order: int = 0
    version_number: int = 1
    is_latest_version: bool = True
    view_count: int = 0
    search_count: int = 0
    reference_count: int = 0
    document_metadata: Optional[Dict[str, Any]] = None
    processing_metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.keywords is None:
            self.keywords = []
        if self.custom_config is None:
            self.custom_config = {}
        if self.document_permissions is None:
            self.document_permissions = {}
        if self.document_metadata is None:
            self.document_metadata = {}
        if self.processing_metadata is None:
            self.processing_metadata = {}


@dataclass
class KBStatisticsModel:
    """知识库统计模型"""

    id: str
    knowledge_base_id: str
    total_documents: int = 0
    total_components: int = 0
    total_chunks: int = 0
    total_photos: int = 0
    total_characters: int = 0
    total_words: int = 0
    total_tokens: int = 0
    total_size_bytes: int = 0
    total_searches: int = 0
    total_views: int = 0
    unique_users_count: int = 0
    avg_search_time_ms: Optional[int] = None
    avg_indexing_time_ms: Optional[int] = None
    last_document_added_at: Optional[datetime] = None
    last_search_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ================================
# 组件抽象层 (Component Abstraction Layer)
# ================================


@dataclass
class ComponentModel:
    """组件模型 - 统一抽象层"""

    id: str
    document_id: str
    component_type: ComponentType
    component_index: int
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ================================
# 组件子类层 (Component Subclass Layer)
# ================================


@dataclass
class ChunkModel:
    """文本块模型 - 组件子类"""

    id: str
    component_id: str
    text_content: str
    char_count: Optional[int] = None
    word_count: Optional[int] = None
    token_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PhotoModel:
    """图片模型 - 组件子类"""

    id: str
    component_id: str
    extracted_asset_id: str
    photo_description: Optional[str] = None
    alt_text: Optional[str] = None
    photo_subtype: str = "image"
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
