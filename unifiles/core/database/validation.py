"""
数据库验证工具

包含用户验证、存储验证等数据库相关的验证功能
"""

from unifiles.core.logging import get_logger

logger = get_logger()


async def validate_user_id(user_id: str) -> bool:
    """验证用户在数据库中是否存在（使用全局连接池）"""
    from unifiles.core.database.connection import get_connection_pool

    try:
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            query = "SELECT EXISTS(SELECT 1 FROM unifiles.users WHERE id = $1)"
            result = await conn.fetchval(query, user_id)
            return result
    except Exception as e:
        logger.error(f"Error validating user_id: {e}")
        return False


async def validate_user_id_in_minio(user_id: str) -> bool:
    """验证用户在 MinIO 中是否存在（检查是否有文件）

    使用统一的 storage 模块进行检查，避免重复创建 MinIO 客户端
    """
    try:
        from unifiles.core.storage import get_storage

        storage = get_storage()
        return await storage.check_user_exists_in_storage(user_id)
    except Exception as e:
        logger.error(f"Error checking user_id in MinIO: {e}")
        return False


async def validate_database_connection() -> bool:
    """验证数据库连接是否正常（使用全局连接池）"""
    try:
        from unifiles.core.database.connection import get_connection_pool

        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database connection validation failed: {e}")
        return False


async def validate_storage_connection() -> bool:
    """验证存储连接是否正常

    使用统一的 storage 模块进行健康检查
    """
    try:
        from unifiles.core.storage import get_storage

        storage = get_storage()
        health = await storage.health_check()
        return health.get("status") in ("healthy", "degraded")
    except Exception as e:
        logger.error(f"Storage connection validation failed: {e}")
        return False
