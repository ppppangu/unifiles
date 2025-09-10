"""
数据库模型定义
提供标准化的数据库操作模型和类型定义
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class FileStatus(Enum):
    """文件状态枚举"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"
    DELETED = "deleted"


class ProcessingStage(Enum):
    """处理阶段枚举"""
    UPLOAD = "upload"
    VALIDATION = "validation"
    PARSING = "parsing"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETION = "completion"


class ProcessingStatus(Enum):
    """处理状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class UserModel:
    """用户模型"""
    id: str
    knowledge_ids: List[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.knowledge_ids is None:
            self.knowledge_ids = []


@dataclass
class KnowledgeBaseModel:
    """知识库模型"""
    id: str
    user_id: str
    name: str
    description: str = ""
    document_ids: List[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.document_ids is None:
            self.document_ids = []


@dataclass
class DocumentModel:
    """文档模型"""
    id: str
    knowledge_base_id: str
    name: str
    text: str = ""
    component_ids: List[str] = None
    hierarchy_path: str = "root"
    markdown_public_url: Optional[str] = None
    raw_file_public_url: Optional[str] = None
    upload_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.component_ids is None:
            self.component_ids = []


@dataclass
class FileModel:
    """文件模型"""
    id: str
    user_id: str
    filename: str
    bytes: int
    object_type: str = "file"
    purpose: str = "assistants"
    status: FileStatus = FileStatus.UPLOADED
    status_details: Optional[str] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None
    raw_file_public_url: Optional[str] = None
    processed_file_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ChunkModel:
    """文本块模型"""
    id: str
    document_id: str
    text: str
    doc_position: Optional[int] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PhotoModel:
    """图片模型"""
    id: str
    document_id: str
    type: str  # "photo" or "table"
    text: str  # 图片描述文本
    base64_image: Optional[str] = None
    embedding: Optional[List[float]] = None
    doc_position: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ProcessingLogModel:
    """处理日志模型"""
    id: str
    file_id: str
    user_id: str
    status: ProcessingStatus
    stage: ProcessingStage
    message: Optional[str] = None
    details: Dict[str, Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.error_info is None:
            self.error_info = {}