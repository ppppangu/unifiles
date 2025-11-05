"""
知识库相关类型

包含知识库模型、文档模型、统计模型等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class KnowledgeBaseStatus(Enum):
    """知识库状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class KnowledgeBaseModel:
    """知识库模型"""

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
    """知识库文档模型"""

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
