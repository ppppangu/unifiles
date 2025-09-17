from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from loguru import logger

from unifiles.core.config.env_config import read_pg_config
from unifiles.core.security.authorization import DatabaseSecurityEnforcer


class SecureFileDBManager:
    """安全增强的文件数据库管理器"""

    def __init__(self):
        """初始化安全数据库管理器"""
        self.pg_config = read_pg_config()
        self.security_enforcer = DatabaseSecurityEnforcer()
        self._connection_pool = None
        self._schema_name = "chunk_schema"  # 从配置中读取

    async def init_connection_pool(self, min_size: int = 5, max_size: int = 20):
        """初始化连接池"""
        if not self._connection_pool:
            try:
                self._connection_pool = await asyncpg.create_pool(
                    **self.pg_config,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30,
                )
                logger.info("Secure database connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise

    @asynccontextmanager
    async def get_connection(self):
        """获取安全的数据库连接"""
        if not self._connection_pool:
            await self.init_connection_pool()

        async with self._connection_pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database operation error: {e}")
                raise

    async def execute_secure_query(
        self, query: str, *args, user_id: Optional[str] = None, operation: Optional[str] = None
    ) -> Any:
        """执行安全的数据库查询"""
        # 审计日志
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "file_operation", user_id, {"query_type": operation}
            )

        async with self.get_connection() as conn:
            return await conn.execute(query, *args)

    async def fetch_one_secure(
        self, query: str, *args, user_id: Optional[str] = None, operation: Optional[str] = None
    ) -> Optional[Dict]:
        """安全获取单条记录"""
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "file_query", user_id, {"query_type": "fetch_one"}
            )

        async with self.get_connection() as conn:
            result = await conn.fetchrow(query, *args)
            return dict(result) if result else None

    async def fetch_many_secure(
        self, query: str, *args, user_id: Optional[str] = None, operation: Optional[str] = None
    ) -> List[Dict]:
        """安全获取多条记录"""
        if user_id and operation:
            self.security_enforcer.audit_log(
                operation, "file_query", user_id, {"query_type": "fetch_many"}
            )

        async with self.get_connection() as conn:
            results = await conn.fetch(query, *args)
            return [dict(row) for row in results]

    async def ensure_user_exists(self, user_id: str) -> None:
        """确保用户在数据库中存在，如果不存在则创建"""
        # 输入验证
        if not user_id or len(user_id.strip()) == 0:
            raise ValueError("Invalid user_id")

        user_id = self.security_enforcer.sanitize_sql_input(user_id)

        try:
            exists = await self.fetch_one_secure(
                f"SELECT EXISTS(SELECT 1 FROM {self._schema_name}.users WHERE id = $1)",
                user_id,
                user_id=user_id,
                operation="user_check",
            )

            if not exists or not exists.get("exists"):
                await self.execute_secure_query(
                    f"INSERT INTO {self._schema_name}.users (id, created_at) VALUES ($1, $2)",
                    user_id,
                    datetime.now(),
                    user_id=user_id,
                    operation="user_creation",
                )
                logger.info(f"Created new user in database: {user_id}")

        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            raise

    async def add_file_record(
        self,
        file_id: str,
        user_id: str,
        filename: str,
        file_size: int,
        content_type: str,
        storage_path: str,
        storage_config_id: str = "minio-default",
    ) -> None:
        """添加文件记录到数据库（安全版本）"""
        try:
            # 输入验证和清理
            file_id = self.security_enforcer.sanitize_sql_input(file_id)
            user_id = self.security_enforcer.sanitize_sql_input(user_id)
            filename = self.security_enforcer.sanitize_sql_input(filename)
            storage_path = self.security_enforcer.sanitize_sql_input(storage_path)

            # 验证文件大小
            if file_size < 0 or file_size > 1024 * 1024 * 1024:  # 1GB限制
                raise ValueError(f"Invalid file size: {file_size}")

            # 确保用户存在
            await self.ensure_user_exists(user_id)

            # 使用事务插入文件记录
            async with self.get_connection() as conn:
                async with conn.transaction():
                    await conn.execute(
                        f"""
                        INSERT INTO {self._schema_name}.files (
                            id, user_id, bytes, filename, mime_type,
                            storage_path, storage_config_id, status, created_at, is_public
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        file_id,
                        user_id,
                        file_size,
                        filename,
                        content_type,
                        storage_path,
                        storage_config_id,
                        "uploaded",
                        datetime.now(),
                        False,  # 默认私有
                    )

            # 记录审计日志
            self.security_enforcer.audit_log(
                "file_creation",
                "files",
                user_id,
                {
                    "file_id": file_id,
                    "filename": filename,
                    "file_size": file_size,
                    "content_type": content_type,
                },
            )

            logger.info(
                f"File record created in database: {file_id} by user: {user_id}"
            )

        except Exception as e:
            logger.error(f"Error adding file record: {e}")
            raise

    async def get_file_record(
        self, file_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """根据文件ID获取文件记录（安全版本）"""
        try:
            file_id = self.security_enforcer.sanitize_sql_input(file_id)

            query = f"""
                SELECT id, filename, bytes, mime_type, storage_path,
                       created_at, user_id, is_public, status
                FROM {self._schema_name}.files
                WHERE id = $1
            """

            result = await self.fetch_one_secure(
                query, file_id, user_id=user_id, operation="file_query"
            )

            return result

        except Exception as e:
            logger.error(f"Error getting file record: {e}")
            raise

    async def get_user_files(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        """获取用户的文件列表（安全版本）"""
        try:
            user_id = self.security_enforcer.sanitize_sql_input(user_id)

            # 验证分页参数
            if limit < 1 or limit > 100:
                raise ValueError("Limit must be between 1 and 100")
            if offset < 0:
                raise ValueError("Offset must be non-negative")

            query = f"""
                SELECT id, filename, bytes, mime_type, storage_path,
                       created_at, user_id, is_public, status
                FROM {self._schema_name}.files
                WHERE user_id = $1 AND status != 'deleted'
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """

            results = await self.fetch_many_secure(
                query, user_id, limit, offset, user_id=user_id, operation="file_list"
            )

            return results

        except Exception as e:
            logger.error(f"Error getting user files: {e}")
            raise

    async def delete_file_record(self, file_id: str, user_id: str) -> None:
        """删除文件记录（安全版本 - 软删除）"""
        try:
            file_id = self.security_enforcer.sanitize_sql_input(file_id)
            user_id = self.security_enforcer.sanitize_sql_input(user_id)

            # 使用软删除而不是物理删除
            async with self.get_connection() as conn, conn.transaction():
                result = await conn.execute(
                    f"""
                        UPDATE {self._schema_name}.files
                        SET status = 'deleted', deleted_at = $3
                        WHERE id = $1 AND user_id = $2 AND status != 'deleted'
                        """,
                    file_id,
                    user_id,
                    datetime.now(),
                )

            # 检查是否实际更新了记录
            rows_affected = int(result.split()[-1]) if result else 0

            if rows_affected == 0:
                logger.warning(
                    f"Attempted to delete non-existent or unauthorized file: {file_id} by user: {user_id}"
                )
            else:
                # 记录审计日志
                self.security_enforcer.audit_log(
                    "file_deletion",
                    "files",
                    user_id,
                    {"file_id": file_id, "deletion_type": "soft_delete"},
                )
                logger.info(f"File record soft-deleted: {file_id} by user: {user_id}")

        except Exception as e:
            logger.error(f"Error deleting file record: {e}")
            raise

    async def update_file_public_status(
        self, file_id: str, is_public: bool, user_id: str
    ) -> None:
        """更新文件的公开访问状态（安全版本）"""
        try:
            file_id = self.security_enforcer.sanitize_sql_input(file_id)
            user_id = self.security_enforcer.sanitize_sql_input(user_id)

            async with self.get_connection() as conn, conn.transaction():
                result = await conn.execute(
                    f"""
                        UPDATE {self._schema_name}.files
                        SET is_public = $3, updated_at = $4
                        WHERE id = $1 AND user_id = $2 AND status != 'deleted'
                        """,
                    file_id,
                    user_id,
                    is_public,
                    datetime.now(),
                )

            rows_affected = int(result.split()[-1]) if result else 0

            if rows_affected == 0:
                raise ValueError(f"File not found or access denied: {file_id}")

            # 记录审计日志
            self.security_enforcer.audit_log(
                "file_public_status_update",
                "files",
                user_id,
                {"file_id": file_id, "is_public": is_public},
            )

            logger.info(
                f"Updated file {file_id} public status to: {is_public} by user: {user_id}"
            )

        except Exception as e:
            logger.error(f"Error updating file public status: {e}")
            raise

    async def get_file_access_info(self, file_id: str) -> Optional[Dict]:
        """获取文件访问信息（安全版本）"""
        try:
            file_id = self.security_enforcer.sanitize_sql_input(file_id)

            query = f"""
                SELECT storage_path, is_public, mime_type, filename, user_id, status
                FROM {self._schema_name}.files
                WHERE id = $1 AND status != 'deleted'
            """

            result = await self.fetch_one_secure(
                query, file_id, operation="file_access_info"
            )

            return result

        except Exception as e:
            logger.error(f"Error getting file access info: {e}")
            raise

    async def update_file_access_info(
        self, file_id: str, user_id: str, **kwargs
    ) -> None:
        """更新文件访问信息（安全可扩展的方法）"""
        try:
            file_id = self.security_enforcer.sanitize_sql_input(file_id)
            user_id = self.security_enforcer.sanitize_sql_input(user_id)

            # 构建动态更新语句
            update_fields = []
            values = [file_id, user_id]
            param_count = 2

            allowed_fields = ["is_public", "status", "mime_type", "filename"]

            for field, value in kwargs.items():
                if field in allowed_fields:
                    param_count += 1
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)

            if update_fields:
                # 添加更新时间
                param_count += 1
                update_fields.append(f"updated_at = ${param_count}")
                values.append(datetime.now())

                query = f"""
                    UPDATE {self._schema_name}.files
                    SET {", ".join(update_fields)}
                    WHERE id = $1 AND user_id = $2 AND status != 'deleted'
                """

                async with self.get_connection() as conn:
                    async with conn.transaction():
                        result = await conn.execute(query, *values)

                rows_affected = int(result.split()[-1]) if result else 0

                if rows_affected == 0:
                    raise ValueError(f"File not found or access denied: {file_id}")

                # 记录审计日志
                self.security_enforcer.audit_log(
                    "file_info_update",
                    "files",
                    user_id,
                    {"file_id": file_id, "updated_fields": list(kwargs.keys())},
                )

                logger.info(
                    f"Updated file access info for {file_id}: {kwargs} by user: {user_id}"
                )

        except Exception as e:
            logger.error(f"Error updating file access info: {e}")
            raise

    async def get_storage_statistics(self, user_id: str) -> Dict[str, Any]:
        """获取用户存储统计信息"""
        try:
            user_id = self.security_enforcer.sanitize_sql_input(user_id)

            query = f"""
                SELECT
                    COUNT(*) as total_files,
                    COALESCE(SUM(bytes), 0) as total_bytes,
                    COUNT(CASE WHEN is_public = true THEN 1 END) as public_files,
                    COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as active_files,
                    COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted_files
                FROM {self._schema_name}.files
                WHERE user_id = $1
            """

            result = await self.fetch_one_secure(
                query, user_id, user_id=user_id, operation="storage_statistics"
            )

            return result or {}

        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            raise

    async def cleanup_deleted_files(self, days_old: int = 30) -> int:
        """清理旧的已删除文件记录"""
        try:
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=days_old)

            async with self.get_connection() as conn, conn.transaction():
                result = await conn.execute(
                    f"""
                        DELETE FROM {self._schema_name}.files
                        WHERE status = 'deleted' AND deleted_at < $1
                        """,
                    cutoff_date,
                )

            cleaned_count = int(result.split()[-1]) if result else 0

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old deleted file records")

            return cleaned_count

        except Exception as e:
            logger.error(f"Error cleaning up deleted files: {e}")
            return 0

    async def close_connection_pool(self):
        """关闭连接池"""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
            logger.info("Secure database connection pool closed")


# 全局安全实例
secure_file_db_manager = SecureFileDBManager()
