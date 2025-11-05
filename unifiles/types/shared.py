"""
跨模块共享的基础类型

这些类型被 core, app, workers 多个模块共同使用。
"""

from enum import Enum


class ProcessingStatus(Enum):
    """处理状态（通用）"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStage(Enum):
    """处理阶段"""

    UPLOAD = "upload"
    VALIDATION = "validation"
    OCR_EXTRACTION = "ocr_extraction"
    MARKDOWN_GENERATION = "markdown_generation"
