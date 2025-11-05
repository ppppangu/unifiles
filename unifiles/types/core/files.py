"""
文件管理相关类型

包含文件模型、文件状态枚举、处理日志等。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from unifiles.types.shared import ProcessingStage, ProcessingStatus


class FileStatus(Enum):
    """文件状态"""

    UPLOADED = "uploaded"
    VALIDATING = "validating"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"
    DELETED = "deleted"


@dataclass
class FileModel:
    """文件模型"""

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
