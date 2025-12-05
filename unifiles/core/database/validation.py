"""
数据库验证工具

包含用户验证、存储验证等数据库相关的验证功能
从 utils/tools.py 迁移而来，职责更明确
"""

import asyncpg

from unifiles.core.logging import get_logger

logger = get_logger()
from minio import Minio


async def validate_user_id(user_id: str) -> bool:
    """验证用户在数据库中是否存在"""
    from unifiles.core.config.env_config import read_pg_config

    pg_config = read_pg_config()
    async with asyncpg.create_pool(**pg_config) as pool, pool.acquire() as conn:
        async with conn.transaction():
            query = "SELECT EXISTS(SELECT 1 FROM unifiles.users WHERE id = $1)"
            result = await conn.fetch(query, user_id)
            return result[0]["exists"]


async def validate_user_id_in_minio(user_id: str) -> bool:
    """验证用户在MinIO中是否存在（检查是否有文件）"""
    from unifiles.core.config.env_config import read_minio_config

    minio_config = read_minio_config()
    minio_client = Minio(
        (
            minio_config["address"]
            if "address" in minio_config
            else f"{minio_config['host']}:{minio_config['port']}"
        ),
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False,
    )
    try:
        # 检查桶内是否存在以用户id命名的目录
        objects = minio_client.list_objects(
            minio_config["bucket_name"], prefix=f"{user_id}/", recursive=False
        )
        return any(True for _ in objects)
    except Exception as e:
        logger.error(f"Error checking user_id in MinIO: {e}")
        return False


async def validate_database_connection() -> bool:
    """验证数据库连接是否正常"""
    try:
        from unifiles.core.config.env_config import read_pg_config

        pg_config = read_pg_config()
        async with asyncpg.create_pool(**pg_config, min_size=1, max_size=1) as pool:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
    except Exception as e:
        logger.error(f"Database connection validation failed: {e}")
        return False


async def validate_storage_connection() -> bool:
    """验证存储连接是否正常"""
    try:
        from unifiles.core.config.env_config import read_minio_config

        minio_config = read_minio_config()
        minio_client = Minio(
            (
                minio_config["address"]
                if "address" in minio_config
                else f"{minio_config['host']}:{minio_config['port']}"
            ),
            access_key=minio_config["access_key"],
            secret_key=minio_config["secret_key"],
            secure=False,
        )

        # 检查桶是否存在
        bucket_exists = minio_client.bucket_exists(minio_config["bucket_name"])
        return bucket_exists
    except Exception as e:
        logger.error(f"Storage connection validation failed: {e}")
        return False
