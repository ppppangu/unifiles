"""
数据库模块
提供统一的数据库操作接口和模型定义
"""

from .manager import DatabaseManager
from .models import (
    UserModel, KnowledgeBaseModel, DocumentModel, FileModel,
    ChunkModel, PhotoModel, ProcessingLogModel,
    FileStatus, ProcessingStage, ProcessingStatus
)

__all__ = [
    'DatabaseManager',
    'UserModel', 'KnowledgeBaseModel', 'DocumentModel', 'FileModel',
    'ChunkModel', 'PhotoModel', 'ProcessingLogModel',
    'FileStatus', 'ProcessingStage', 'ProcessingStatus'
]