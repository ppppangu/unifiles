import asyncpg
from loguru import logger
from minio import Minio

# ======================================
# ===========  数据库验证工具 ============
# ======================================


# 验证用户id在数据库中是否存在
async def validate_user_id(user_id: str) -> bool:
    """验证用户在数据库中是否存在"""
    from unifiles.core.config.env_config import read_pg_config

    pg_config = read_pg_config()
    async with asyncpg.create_pool(**pg_config) as pool, pool.acquire() as conn:
        async with conn.transaction():
            query = "SELECT EXISTS(SELECT 1 FROM chunk_schema.users WHERE id = $1)"
            result = await conn.fetch(query, user_id)
            return result[0]["exists"]


# 验证用户id在minio中是否存在, 看桶内是否存在以用户id命名的目录
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
