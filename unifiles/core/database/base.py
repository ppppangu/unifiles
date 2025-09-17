from abc import ABC
from typing import Any, Dict, List, Optional

import asyncpg
from loguru import logger

from unifiles.core.config.env_config import read_pg_config


class DatabaseManager(ABC):
    """数据库操作的抽象基类"""

    def __init__(self):
        self.pg_config = read_pg_config()

    async def get_connection(self) -> asyncpg.Connection:
        """获取数据库连接"""
        return await asyncpg.connect(**self.pg_config)

    async def execute_query(self, query: str, *args) -> Any:
        """执行查询并返回结果"""
        conn = None
        try:
            conn = await self.get_connection()
            return await conn.execute(query, *args)
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def fetch_one(self, query: str, *args) -> Optional[Dict]:
        """获取单条记录"""
        conn = None
        try:
            conn = await self.get_connection()
            result = await conn.fetchrow(query, *args)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching one record: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def fetch_many(self, query: str, *args) -> List[Dict]:
        """获取多条记录"""
        conn = None
        try:
            conn = await self.get_connection()
            results = await conn.fetch(query, *args)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching multiple records: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def fetch_value(self, query: str, *args) -> Any:
        """获取单个值"""
        conn = None
        try:
            conn = await self.get_connection()
            return await conn.fetchval(query, *args)
        except Exception as e:
            logger.error(f"Error fetching value: {e}")
            raise
        finally:
            if conn:
                await conn.close()


class FileDBManager(DatabaseManager):
    """文件相关的数据库操作管理器"""

    async def ensure_user_exists(self, user_id: str) -> None:
        """确保用户在数据库中存在，如果不存在则创建"""
        exists = await self.fetch_value(
            "SELECT EXISTS(SELECT 1 FROM chunk_schema.users WHERE id = $1)", user_id
        )
        if not exists:
            await self.execute_query(
                "INSERT INTO chunk_schema.users (id) VALUES ($1)", user_id
            )
            logger.info(f"Created new user in database: {user_id}")

    async def add_file_record(
        self,
        file_id: str,
        user_id: str,
        filename: str,
        file_size: int,
        content_type: str,
        object_path: str,
        public_url: str,
    ) -> None:
        """添加文件记录到数据库"""
        await self.ensure_user_exists(user_id)
        await self.execute_query(
            """
            INSERT INTO chunk_schema.files (
                id, user_id, bytes, filename, mime_type,
                file_path, raw_file_public_url, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            file_id,
            user_id,
            file_size,
            filename,
            content_type,
            object_path,
            public_url,
            "uploaded",
        )
        logger.info(f"File record created in database: {file_id}")

    async def get_file_record(self, file_id: str) -> Optional[Dict]:
        """根据文件ID获取文件记录"""
        return await self.fetch_one(
            """
            SELECT id, filename, bytes, mime_type, raw_file_public_url,
                   file_path, created_at, user_id
            FROM chunk_schema.files
            WHERE id = $1
            """,
            file_id,
        )

    async def get_user_files(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict]:
        """获取用户的文件列表"""
        return await self.fetch_many(
            """
            SELECT id, filename, bytes, mime_type, raw_file_public_url,
                   file_path, created_at, user_id
            FROM chunk_schema.files
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

    async def delete_file_record(self, file_id: str) -> None:
        """删除文件记录"""
        result = await self.execute_query(
            "DELETE FROM chunk_schema.files WHERE id = $1", file_id
        )
        if " 0" in result:
            logger.warning(f"Attempted to delete non-existent file record: {file_id}")
        else:
            logger.info(f"File record deleted from database: {file_id}")

    async def update_file_public_url(self, file_id: str, public_url: str) -> None:
        """更新文件的公共访问链接"""
        await self.execute_query(
            "UPDATE chunk_schema.files SET raw_file_public_url = $2 WHERE id = $1",
            file_id,
            public_url,
        )
        logger.info(f"Updated public URL for file {file_id}")

    async def get_file_object_path(self, file_id: str) -> Optional[str]:
        """获取文件的对象路径"""
        result = await self.fetch_value(
            "SELECT file_path FROM chunk_schema.files WHERE id = $1", file_id
        )
        return result

    async def update_file_access_info(self, file_id: str, **kwargs) -> None:
        """更新文件访问信息（可扩展的方法）"""
        # 构建动态更新语句
        update_fields = []
        values = []
        param_count = 1

        for field, value in kwargs.items():
            if field in ["is_public", "status", "mime_type"]:
                update_fields.append(f"{field} = ${param_count + 1}")
                values.append(value)
                param_count += 1

        if update_fields:
            query = f"UPDATE chunk_schema.files SET {', '.join(update_fields)} WHERE id = $1"
            await self.execute_query(query, file_id, *values)
            logger.info(f"Updated file access info for {file_id}: {kwargs}")

    async def update_file_public_status(self, file_id: str, is_public: bool) -> None:
        """更新文件的公开访问状态"""
        await self.execute_query(
            "UPDATE chunk_schema.files SET is_public = $2 WHERE id = $1",
            file_id,
            is_public,
        )
        logger.info(f"Updated file {file_id} public status to: {is_public}")

    async def get_file_access_info(self, file_id: str) -> Optional[Dict]:
        """获取文件访问信息"""
        return await self.fetch_one(
            """
            SELECT storage_path, is_public, mime_type, filename
            FROM chunk_schema.files
            WHERE id = $1
            """,
            file_id,
        )


# 全局实例
file_db_manager = FileDBManager()
