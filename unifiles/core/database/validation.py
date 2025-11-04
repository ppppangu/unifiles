"""
数据库验证工具

包含用户验证、存储验证等数据库相关的验证功能
从 utils/tools.py 迁移而来，职责更明确
"""

import asyncpg
from loguru import logger
from minio import Minio

from unifiles.config import settings


async def validate_user_id(user_id: str) -> bool:
    """验证用户在数据库中是否存在"""
    async with asyncpg.create_pool(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.user,
        password=settings.database.password,
        database=settings.database.database,
    ) as pool, pool.acquire() as conn:
        async with conn.transaction():
            query = "SELECT EXISTS(SELECT 1 FROM unifiles.users WHERE id = $1)"
            result = await conn.fetch(query, user_id)
            return result[0]["exists"]


async def validate_user_id_in_minio(user_id: str) -> bool:
    """验证用户在MinIO中是否存在（检查是否有文件）"""
    minio_client = Minio(
        settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
    )
    try:
        # 检查桶内是否存在以用户id命名的目录
        objects = minio_client.list_objects(
            settings.minio.bucket_name, prefix=f"{user_id}/", recursive=False
        )
        return any(True for _ in objects)
    except Exception as e:
        logger.error(f"Error checking user_id in MinIO: {e}")
        return False


async def validate_database_connection() -> bool:
    """验证数据库连接是否正常"""
    try:
        async with asyncpg.create_pool(
            host=settings.database.host,
            port=settings.database.port,
            user=settings.database.user,
            password=settings.database.password,
            database=settings.database.database,
            min_size=1,
            max_size=1,
        ) as pool:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
    except Exception as e:
        logger.error(f"Database connection validation failed: {e}")
        return False


async def validate_storage_connection() -> bool:
    """验证存储连接是否正常"""
    try:
        minio_client = Minio(
            settings.minio.endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            secure=settings.minio.secure,
        )

        # 检查桶是否存在
        bucket_exists = minio_client.bucket_exists(settings.minio.bucket_name)
        return bucket_exists
    except Exception as e:
        logger.error(f"Storage connection validation failed: {e}")
        return False
