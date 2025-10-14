"""
统一数据库管理器
提供单一入口访问所有数据库操作
"""

from .file_manager import FileDBManager, unified_file_db_manager
from .knowledge_base_manager import (
    KnowledgeBaseDBManager,
    unified_kb_db_manager,
)
from .user_manager import UserDBManager, unified_user_db_manager


class UnifiedDatabaseManager:
    """
    统一数据库管理器 - 提供单一入口访问所有数据库操作

    这个类整合了文件管理和知识库管理的功能，提供统一的接口。
    """

    def __init__(self):
        """初始化统一数据库管理器"""
        self._file_manager = unified_file_db_manager
        self._kb_manager = unified_kb_db_manager
        self._user_manager = unified_user_db_manager

    @property
    def files(self) -> FileDBManager:
        """
        获取文件管理器

        Returns:
            FileDBManager: 文件数据库管理器实例
        """
        return self._file_manager

    @property
    def knowledge_bases(self) -> KnowledgeBaseDBManager:
        """
        获取知识库管理器

        Returns:
            KnowledgeBaseDBManager: 知识库数据库管理器实例
        """
        return self._kb_manager

    @property
    def users(self) -> UserDBManager:
        """
        获取用户管理器

        Returns:
            UserDBManager: 用户数据库管理器实例
        """
        return self._user_manager

    # 向后兼容的方法 - 直接代理到文件管理器
    async def ensure_user_exists(self, user_id: str):
        """确保用户存在（代理到用户管理器）"""
        return await self._user_manager.ensure_user_exists(user_id)

    async def add_file_record(
        self,
        file_id: str,
        user_id: str,
        filename: str,
        file_size: int,
        content_type: str,
        storage_path: str,
        storage_config_id: str = None,
    ):
        """添加文件记录（代理到文件管理器）"""
        return await self._file_manager.add_file_record(
            file_id, user_id, filename, file_size, content_type, storage_path, storage_config_id
        )

    async def get_file_record(self, file_id: str, user_id: str = None):
        """获取文件记录（代理到文件管理器）"""
        return await self._file_manager.get_file_record(file_id, user_id)

    async def get_user_files(self, user_id: str, limit: int = 50, offset: int = 0):
        """获取用户文件列表（代理到文件管理器）"""
        return await self._file_manager.get_user_files(user_id, limit, offset)

    async def delete_file_record(self, file_id: str, user_id: str):
        """删除文件记录（代理到文件管理器）"""
        return await self._file_manager.delete_file_record(file_id, user_id)

    async def update_file_public_status(
        self, file_id: str, is_public: bool, user_id: str = None
    ):
        """更新文件公开状态（代理到文件管理器）"""
        return await self._file_manager.update_file_public_status(
            file_id, is_public, user_id
        )

    async def get_file_access_info(self, file_id: str):
        """获取文件访问信息（代理到文件管理器）"""
        return await self._file_manager.get_file_access_info(file_id)

    async def update_file_access_info(self, file_id: str, user_id: str, **kwargs):
        """更新文件访问信息（代理到文件管理器）"""
        return await self._file_manager.update_file_access_info(
            file_id, user_id, **kwargs
        )

    async def get_storage_statistics(self, user_id: str):
        """获取存储统计信息（代理到文件管理器）"""
        return await self._file_manager.get_storage_statistics(user_id)

    # 知识库相关方法
    async def create_knowledge_base(self, kb_model):
        """创建知识库（代理到知识库管理器）"""
        return await self._kb_manager.create_knowledge_base(kb_model)

    async def get_knowledge_base(self, kb_id: str):
        """获取知识库（代理到知识库管理器）"""
        return await self._kb_manager.get_knowledge_base(kb_id)

    async def create_document(self, doc_model):
        """创建文档（代理到知识库管理器）"""
        return await self._kb_manager.create_document(doc_model)

    async def get_document(self, doc_id: str):
        """获取文档（代理到知识库管理器）"""
        return await self._kb_manager.get_document(doc_id)

    async def save_chunk(self, chunk_model):
        """保存文本块（代理到知识库管理器）"""
        return await self._kb_manager.save_chunk(chunk_model)

    async def save_photo(self, photo_model):
        """保存图片（代理到知识库管理器）"""
        return await self._kb_manager.save_photo(photo_model)

    async def create_processing_log(self, log_model):
        """创建处理日志（代理到知识库管理器）"""
        return await self._kb_manager.create_processing_log(log_model)

    async def update_processing_log(
        self, log_id: str, status, message: str = None, error_info: dict = None
    ):
        """更新处理日志（代理到知识库管理器）"""
        return await self._kb_manager.update_processing_log(
            log_id, status, message, error_info
        )


# 全局统一管理器实例
unified_db_manager = UnifiedDatabaseManager()
