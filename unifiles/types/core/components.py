"""
组件系统相关类型

包含组件抽象模型、文本块模型、图片模型等。
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class ComponentType(Enum):
    """组件类型"""

    CHUNK = "chunk"
    PHOTO = "photo"


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
