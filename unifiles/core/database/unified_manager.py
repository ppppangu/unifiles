"""
统一数据库管理器
提供单一入口访问所有数据库操作
"""

from .file_manager import FileDBManager, unified_file_db_manager
from .knowledge_base_manager import KnowledgeBaseDBManager, unified_kb_db_manager
from .user_manager import UserDBManager, unified_user_db_manager


class UnifiedDatabaseManager:
    """
    统一数据库管理器 - 提供单一入口访问所有数据库操作

    通过属性访问具体的管理器:
    - db.files: 文件管理器
    - db.knowledge_bases: 知识库管理器
    - db.users: 用户管理器

    示例:
        db = unified_db_manager
        await db.files.get_file_record(file_id)
        await db.knowledge_bases.create_knowledge_base(kb_model)
        await db.users.ensure_user_exists(user_id)
    """

    def __init__(self):
        """初始化统一数据库管理器"""
        self._file_manager = unified_file_db_manager
        self._kb_manager = unified_kb_db_manager
        self._user_manager = unified_user_db_manager

    @property
    def files(self) -> FileDBManager:
        """获取文件管理器"""
        return self._file_manager

    @property
    def knowledge_bases(self) -> KnowledgeBaseDBManager:
        """获取知识库管理器"""
        return self._kb_manager

    @property
    def users(self) -> UserDBManager:
        """获取用户管理器"""
        return self._user_manager

    # 保留最常用的快捷方法
    async def ensure_user_exists(self, user_id: str):
        """确保用户存在（快捷方法）"""
        return await self._user_manager.ensure_user_exists(user_id)

    async def get_file_record(self, file_id: str, user_id: str = None):
        """获取文件记录（快捷方法）"""
        return await self._file_manager.get_file_record(file_id, user_id)

    async def get_knowledge_base(self, kb_id: str):
        """获取知识库（快捷方法）"""
        return await self._kb_manager.get_knowledge_base(kb_id)


# 全局统一管理器实例
unified_db_manager = UnifiedDatabaseManager()
