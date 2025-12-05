"""
数据库管理器基类
提供通用的数据库操作方法和安全特性
"""

from abc import ABC
from typing import Any, Dict, List, Optional

from unifiles.core.logging import get_logger

logger = get_logger()

from .connection import get_connection_pool


class BaseDBManager(ABC):
    """数据库管理器抽象基类 - 提供通用的数据库操作和安全特性"""

    def __init__(self):
        """初始化数据库管理器"""
        self._pool = None
        self._schema_name = "unifiles"
        self._security_enforcer = None

    @property
    def security_enforcer(self):
        """Lazy load security enforcer to avoid circular imports"""
        if self._security_enforcer is None:
            from unifiles.core.security.authorization import DatabaseSecurityEnforcer

            self._security_enforcer = DatabaseSecurityEnforcer()
        return self._security_enforcer

    async def _ensure_pool(self):
        """确保连接池已初始化"""
        if self._pool is None:
            self._pool = await get_connection_pool()

    async def get_connection(self):
        """
        获取数据库连接（使用连接池）

        Returns:
            async context manager yielding asyncpg.Connection
        """
        await self._ensure_pool()
        return self._pool.acquire()

    async def execute_query(
        self,
        query: str,
        *args,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> Any:
        """
        执行查询并返回结果

        Args:
            query: SQL查询语句
            *args: 查询参数
            user_id: 用户ID（用于审计）
            operation: 操作类型（用于审计）

        Returns:
            查询执行结果
        """
        # 审计日志
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "database_operation", user_id, {"query_type": operation}
            )

        async with await self.get_connection() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"Error executing query: {e}")
                raise

    async def fetch_one(
        self,
        query: str,
        *args,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        获取单条记录

        Args:
            query: SQL查询语句
            *args: 查询参数
            user_id: 用户ID（用于审计）
            operation: 操作类型（用于审计）

        Returns:
            单条记录的字典，如果不存在则返回None
        """
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "database_query", user_id, {"query_type": "fetch_one"}
            )

        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(query, *args)
                return dict(result) if result else None
            except Exception as e:
                logger.error(f"Error fetching one record: {e}")
                raise

    async def fetch_many(
        self,
        query: str,
        *args,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> List[Dict]:
        """
        获取多条记录

        Args:
            query: SQL查询语句
            *args: 查询参数
            user_id: 用户ID（用于审计）
            operation: 操作类型（用于审计）

        Returns:
            记录列表
        """
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "database_query", user_id, {"query_type": "fetch_many"}
            )

        async with await self.get_connection() as conn:
            try:
                results = await conn.fetch(query, *args)
                return [dict(row) for row in results]
            except Exception as e:
                logger.error(f"Error fetching multiple records: {e}")
                raise

    async def fetch_value(
        self,
        query: str,
        *args,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> Any:
        """
        获取单个值

        Args:
            query: SQL查询语句
            *args: 查询参数
            user_id: 用户ID（用于审计）
            operation: 操作类型（用于审计）

        Returns:
            单个值
        """
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "database_query", user_id, {"query_type": "fetch_value"}
            )

        async with await self.get_connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                logger.error(f"Error fetching value: {e}")
                raise

    def sanitize_input(self, value: str) -> str:
        """
        清理输入以防止SQL注入

        Args:
            value: 待清理的字符串

        Returns:
            清理后的字符串
        """
        return self.security_enforcer.sanitize_sql_input(value)

    def validate_pagination(self, limit: int, offset: int, max_limit: int = 100):
        """
        验证分页参数

        Args:
            limit: 限制数量
            offset: 偏移量
            max_limit: 最大限制数量

        Raises:
            ValueError: 如果参数无效
        """
        if limit < 1 or limit > max_limit:
            raise ValueError(f"Limit must be between 1 and {max_limit}")
        if offset < 0:
            raise ValueError("Offset must be non-negative")
