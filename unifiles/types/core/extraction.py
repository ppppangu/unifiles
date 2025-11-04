"""
内容提取相关类型

包含提取文档模型、提取资源模型、提取状态等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ExtractionStatus(Enum):
    """提取状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ExtractedDocumentModel:
    """提取文档模型"""

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
    """提取资源模型（图片、表格等）"""

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
