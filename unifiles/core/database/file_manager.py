"""
文件数据库管理器
整合所有文件相关的数据库操作，包含安全特性
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from .base_manager import BaseDBManager


class FileDBManager(BaseDBManager):
    """统一的文件数据库管理器 - 整合了安全特性和完整功能"""

    async def ensure_user_exists(self, user_id: str) -> None:
        """
        确保用户在数据库中存在，如果不存在则创建

        Args:
            user_id: 用户ID

        Raises:
            ValueError: 如果user_id无效
        """
        # 输入验证
        if not user_id or len(user_id.strip()) == 0:
            raise ValueError("Invalid user_id")

        user_id = self.sanitize_input(user_id)

        try:
            exists = await self.fetch_one(
                f"SELECT EXISTS(SELECT 1 FROM {self._schema_name}.users WHERE id = $1)",
                user_id,
                user_id=user_id,
                operation="user_check",
            )

            if not exists or not exists.get("exists"):
                await self.execute_query(
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
        storage_config_id: Optional[str] = None,
    ) -> None:
        """
        添加文件记录到数据库（统一版本）

        Args:
            file_id: 文件ID
            user_id: 用户ID
            filename: 文件名
            file_size: 文件大小（字节）
            content_type: MIME类型
            storage_path: 存储路径
            storage_config_id: 存储配置ID（可选）

        Raises:
            ValueError: 如果参数无效
        """
        try:
            # 输入验证和清理
            file_id = self.sanitize_input(file_id)
            user_id = self.sanitize_input(user_id)
            filename = self.sanitize_input(filename)
            storage_path = self.sanitize_input(storage_path)

            # 验证文件大小
            if file_size < 0 or file_size > 1024 * 1024 * 1024:  # 1GB限制
                raise ValueError(f"Invalid file size: {file_size}")

            # 确保用户存在
            await self.ensure_user_exists(user_id)

            # 使用事务插入文件记录
            async with await self.get_connection() as conn:
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
                        "active",
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
        """
        根据文件ID获取文件记录

        Args:
            file_id: 文件ID
            user_id: 用户ID（用于审计，可选）

        Returns:
            文件记录字典，如果不存在则返回None
        """
        try:
            file_id = self.sanitize_input(file_id)

            query = f"""
                SELECT id, filename, bytes, mime_type, storage_path,
                       created_at, user_id, is_public, status, storage_config_id
                FROM {self._schema_name}.files
                WHERE id = $1
            """

            result = await self.fetch_one(
                query, file_id, user_id=user_id, operation="file_query"
            )

            return result

        except Exception as e:
            logger.error(f"Error getting file record: {e}")
            raise

    async def get_user_files(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        """
        获取用户的文件列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            文件记录列表

        Raises:
            ValueError: 如果分页参数无效
        """
        try:
            user_id = self.sanitize_input(user_id)

            # 验证分页参数
            self.validate_pagination(limit, offset)

            query = f"""
                SELECT id, filename, bytes, mime_type, storage_path,
                       created_at, user_id, is_public, status, storage_config_id
                FROM {self._schema_name}.files
                WHERE user_id = $1 AND status != 'deleted'
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """

            results = await self.fetch_many(
                query, user_id, limit, offset, user_id=user_id, operation="file_list"
            )

            return results

        except Exception as e:
            logger.error(f"Error getting user files: {e}")
            raise

    async def delete_file_record(self, file_id: str, user_id: str) -> None:
        """
        删除文件记录（软删除）

        Args:
            file_id: 文件ID
            user_id: 用户ID

        Raises:
            ValueError: 如果文件不存在或无权限
        """
        try:
            file_id = self.sanitize_input(file_id)
            user_id = self.sanitize_input(user_id)

            # 使用软删除而不是物理删除
            async with await self.get_connection() as conn:
                async with conn.transaction():
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
        self, file_id: str, is_public: bool, user_id: Optional[str] = None
    ) -> None:
        """
        更新文件的公开访问状态

        Args:
            file_id: 文件ID
            is_public: 是否公开
            user_id: 用户ID（如果提供，会验证权限）

        Raises:
            ValueError: 如果文件不存在或无权限
        """
        try:
            file_id = self.sanitize_input(file_id)

            if user_id:
                user_id = self.sanitize_input(user_id)
                # 包含用户验证的更新
                async with await self.get_connection() as conn:
                    async with conn.transaction():
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
            else:
                # 不验证用户的更新（向后兼容）
                await self.execute_query(
                    f"UPDATE {self._schema_name}.files SET is_public = $2, updated_at = $3 WHERE id = $1",
                    file_id,
                    is_public,
                    datetime.now(),
                )
                logger.info(f"Updated file {file_id} public status to: {is_public}")

        except Exception as e:
            logger.error(f"Error updating file public status: {e}")
            raise

    async def get_file_access_info(self, file_id: str) -> Optional[Dict]:
        """
        获取文件访问信息

        Args:
            file_id: 文件ID

        Returns:
            文件访问信息字典
        """
        try:
            file_id = self.sanitize_input(file_id)

            query = f"""
                SELECT storage_path, is_public, mime_type, filename, user_id, status, storage_config_id
                FROM {self._schema_name}.files
                WHERE id = $1 AND status != 'deleted'
            """

            result = await self.fetch_one(
                query, file_id, operation="file_access_info"
            )

            return result

        except Exception as e:
            logger.error(f"Error getting file access info: {e}")
            raise

    async def update_file_access_info(
        self, file_id: str, user_id: str, **kwargs
    ) -> None:
        """
        更新文件访问信息（安全可扩展的方法）

        Args:
            file_id: 文件ID
            user_id: 用户ID
            **kwargs: 要更新的字段

        Raises:
            ValueError: 如果文件不存在或无权限
        """
        try:
            file_id = self.sanitize_input(file_id)
            user_id = self.sanitize_input(user_id)

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

                async with await self.get_connection() as conn:
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
        """
        获取用户存储统计信息

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        try:
            user_id = self.sanitize_input(user_id)

            query = f"""
                SELECT
                    COUNT(*) as total_files,
                    COALESCE(SUM(bytes), 0) as total_bytes,
                    COUNT(CASE WHEN is_public = true THEN 1 END) as public_files,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_files,
                    COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted_files
                FROM {self._schema_name}.files
                WHERE user_id = $1
            """

            result = await self.fetch_one(
                query, user_id, user_id=user_id, operation="storage_statistics"
            )

            return result or {}

        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            raise

    async def cleanup_deleted_files(self, days_old: int = 30) -> int:
        """
        清理旧的已删除文件记录

        Args:
            days_old: 删除多少天前的记录

        Returns:
            清理的记录数量
        """
        try:
            from datetime import timedelta

            cutoff_date = datetime.now() - timedelta(days=days_old)

            async with await self.get_connection() as conn:
                async with conn.transaction():
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


# 全局实例
unified_file_db_manager = FileDBManager()
