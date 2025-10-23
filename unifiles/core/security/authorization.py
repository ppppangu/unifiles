from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from unifiles.core.logging import get_logger
logger = get_logger()


class FileAccessControl:
    """文件访问控制管理器"""

    @staticmethod
    async def verify_file_access(
        user_id: str, file_id: str, operation: str
    ) -> Dict[str, Any]:
        """
        验证用户对文件的访问权限

        Args:
            user_id: 用户ID
            file_id: 文件ID
            operation: 操作类型 (read, write, delete, update)

        Returns:
            文件记录和权限信息

        Raises:
            HTTPException: 权限验证失败时抛出
        """
        from unifiles.core.database import file_db_manager

        # 获取文件记录
        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            logger.warning(
                f"File access denied - file not found: {file_id} by user: {user_id}"
            )
            raise HTTPException(status_code=404, detail="File not found")

        # 验证所有权
        file_owner = file_record.get("user_id")
        if file_owner != user_id:
            logger.warning(
                f"File access denied - ownership mismatch: {file_id} owner: {file_owner} accessor: {user_id}"
            )
            raise HTTPException(
                status_code=403, detail="Access denied: insufficient permissions"
            )

        # 根据操作类型进行额外验证
        if operation == "delete" and file_record.get("is_locked", False):
            raise HTTPException(status_code=409, detail="Cannot delete locked file")

        logger.info(
            f"File access granted: {file_id} operation: {operation} user: {user_id}"
        )
        return file_record

    @staticmethod
    async def verify_public_file_access(file_id: str) -> Dict[str, Any]:
        """
        验证公共文件访问权限

        Args:
            file_id: 文件ID

        Returns:
            文件记录

        Raises:
            HTTPException: 权限验证失败时抛出
        """
        from unifiles.core.database import file_db_manager

        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        if not file_record.get("is_public", False):
            raise HTTPException(
                status_code=403, detail="File is not publicly accessible"
            )

        return file_record

    @staticmethod
    def extract_user_context(request: Request) -> Dict[str, Any]:
        """
        从请求中提取用户上下文信息

        Args:
            request: FastAPI请求对象

        Returns:
            用户上下文字典
        """
        user_context = {
            "user_id": getattr(request.state, "user_id", None),
            "ip_address": getattr(request.state, "client_ip", None),
            "user_agent": request.headers.get("user-agent", ""),
            "request_id": getattr(request.state, "request_id", None),
        }

        if not user_context["user_id"]:
            raise HTTPException(status_code=401, detail="Authentication required")

        return user_context


class DatabaseSecurityEnforcer:
    """数据库安全执行器"""

    @staticmethod
    def sanitize_sql_input(value: str) -> str:
        """
        清理SQL输入防止注入攻击

        Args:
            value: 输入值

        Returns:
            清理后的值
        """
        if not isinstance(value, str):
            return value

        # 移除危险字符
        dangerous_chars = ["--", ";", "/*", "*/", "xp_", "sp_"]
        cleaned_value = value

        for char in dangerous_chars:
            cleaned_value = cleaned_value.replace(char, "")

        return cleaned_value.strip()

    @staticmethod
    def validate_schema_access(schema_name: str, allowed_schemas: Optional[list] = None) -> bool:
        """
        验证数据库模式访问权限

        Args:
            schema_name: 模式名称
            allowed_schemas: 允许访问的模式列表

        Returns:
            是否允许访问
        """
        if allowed_schemas is None:
            allowed_schemas = ["unifiles", "public"]

        return schema_name in allowed_schemas

    @staticmethod
    def audit_log(operation: str, table: str, user_id: str, details: Optional[dict] = None):
        """
        记录数据库操作审计日志

        Args:
            operation: 操作类型
            table: 表名
            user_id: 用户ID
            details: 操作详情
        """
        logger.info(
            f"DB_AUDIT: {operation} on {table} by {user_id}",
            extra={
                "operation": operation,
                "table": table,
                "user_id": user_id,
                "details": details or {},
            },
        )


# 安全的数据库连接管理器
from contextlib import asynccontextmanager

import asyncpg


class SecureDatabaseManager:
    """安全的数据库管理器"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self._connection_pool = None

    async def init_pool(self, min_size: int = 5, max_size: int = 20):
        """初始化连接池"""
        if not self._connection_pool:
            self._connection_pool = await asyncpg.create_pool(
                **self.db_manager.pg_config,
                min_size=min_size,
                max_size=max_size,
                command_timeout=30,
            )

    @asynccontextmanager
    async def get_connection(self):
        """获取安全的数据库连接"""
        if not self._connection_pool:
            await self.init_pool()

        async with self._connection_pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database operation error: {e}")
                raise

    async def execute_secure_query(
        self, query: str, *args, user_id: Optional[str] = None, operation: Optional[str] = None
    ):
        """执行安全的数据库查询"""
        # 审计日志
        if user_id and operation:
            DatabaseSecurityEnforcer.audit_log(
                operation, "file_operation", user_id, {"query_type": operation}
            )

        async with self.get_connection() as conn:
            return await conn.execute(query, *args)

    async def close_pool(self):
        """关闭连接池"""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
