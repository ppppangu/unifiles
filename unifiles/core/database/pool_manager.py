"""
全局连接池管理器 - 单例模式

统一管理 PostgreSQL 和 Redis 连接池，避免资源浪费

特性：
- 单例模式，全局唯一实例
- 异步初始化和清理
- 健康检查
- 连接池监控
"""

import asyncio
from typing import Optional
from loguru import logger

try:
    import asyncpg
    from asyncpg import Pool as PGPool
except ImportError:
    asyncpg = None
    PGPool = None

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
except ImportError:
    redis = None
    Redis = None

from unifiles.config import settings


class ConnectionPoolManager:
    """
    全局连接池管理器

    单例模式，整个应用共享一个PostgreSQL和Redis连接池

    使用示例:
    ```python
    from unifiles.core.database.pool_manager import get_pool_manager

    pool_manager = await get_pool_manager()
    await pool_manager.initialize()

    # 使用PostgreSQL
    async with pool_manager.pg_pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM users")

    # 使用Redis
    await pool_manager.redis.set("key", "value")

    # 应用关闭时
    await pool_manager.close()
    ```
    """

    _instance: Optional["ConnectionPoolManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._pg_pool: Optional[PGPool] = None
        self._redis_client: Optional[Redis] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> "ConnectionPoolManager":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """初始化所有连接池（幂等操作）"""
        if self._initialized:
            logger.debug("ConnectionPoolManager already initialized")
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info("Initializing ConnectionPoolManager...")

            # 初始化PostgreSQL连接池
            await self._init_pg_pool()

            # 初始化Redis连接
            await self._init_redis()

            self._initialized = True
            logger.success("ConnectionPoolManager initialized successfully")

    async def _init_pg_pool(self):
        """初始化PostgreSQL连接池"""
        if asyncpg is None:
            logger.warning("asyncpg not installed, PostgreSQL pool will not be available")
            return

        try:
            self._pg_pool = await asyncpg.create_pool(
                host=settings.database.host,
                port=settings.database.port,
                database=settings.database.database,
                user=settings.database.user,
                password=settings.database.password,
                min_size=settings.database.min_pool_size,
                max_size=settings.database.max_pool_size,
                command_timeout=settings.database.command_timeout,
            )

            logger.info(
                f"PostgreSQL pool created: {settings.database.host}:{settings.database.port}/{settings.database.database} "
                f"(pool: {settings.database.min_pool_size}-{settings.database.max_pool_size})"
            )

        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise

    async def _init_redis(self):
        """初始化Redis连接"""
        if redis is None:
            logger.warning("redis package not installed, Redis will not be available")
            return

        try:
            self._redis_client = await redis.from_url(
                settings.redis_url,
                max_connections=settings.redis.max_connections,
                socket_timeout=settings.redis.socket_timeout,
                socket_connect_timeout=settings.redis.socket_connect_timeout,
                socket_keepalive=True,
                retry_on_timeout=True,
                health_check_interval=30,
                decode_responses=False,  # 队列需要处理二进制
            )

            # 测试连接
            await self._redis_client.ping()

            logger.info(
                f"Redis connected: {settings.redis.host}:{settings.redis.port} "
                f"(db={settings.redis.db}, max_connections={settings.redis.max_connections})"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    @property
    def pg_pool(self) -> PGPool:
        """获取PostgreSQL连接池"""
        if not self._initialized:
            raise RuntimeError("ConnectionPoolManager not initialized, call initialize() first")

        if self._pg_pool is None:
            raise RuntimeError("PostgreSQL pool not available")

        return self._pg_pool

    @property
    def redis(self) -> Redis:
        """获取Redis客户端"""
        if not self._initialized:
            raise RuntimeError("ConnectionPoolManager not initialized, call initialize() first")

        if self._redis_client is None:
            raise RuntimeError("Redis client not available")

        return self._redis_client

    async def health_check(self) -> dict:
        """健康检查"""
        health = {
            "postgresql": {"status": "unknown"},
            "redis": {"status": "unknown"},
        }

        # PostgreSQL健康检查
        if self._pg_pool:
            try:
                async with self._pg_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health["postgresql"] = {
                    "status": "healthy",
                    "pool_size": self._pg_pool.get_size(),
                    "free_connections": self._pg_pool.get_idle_size(),
                    "max_size": settings.database.max_pool_size,
                }
            except Exception as e:
                health["postgresql"] = {"status": "unhealthy", "error": str(e)}

        # Redis健康检查
        if self._redis_client:
            try:
                await self._redis_client.ping()
                info = await self._redis_client.info()
                health["redis"] = {
                    "status": "healthy",
                    "used_memory_human": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                }
            except Exception as e:
                health["redis"] = {"status": "unhealthy", "error": str(e)}

        return health

    async def close(self):
        """关闭所有连接池"""
        if not self._initialized:
            return

        logger.info("Closing ConnectionPoolManager...")

        # 关闭PostgreSQL连接池
        if self._pg_pool:
            try:
                await self._pg_pool.close()
                logger.info("PostgreSQL pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")

        # 关闭Redis连接
        if self._redis_client:
            try:
                await self._redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

        self._initialized = False
        logger.info("ConnectionPoolManager closed")


# ===== 便捷函数 =====

_pool_manager: Optional[ConnectionPoolManager] = None


async def get_pool_manager() -> ConnectionPoolManager:
    """获取全局连接池管理器单例"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = await ConnectionPoolManager.get_instance()
    return _pool_manager


async def get_pg_pool() -> PGPool:
    """快捷获取PostgreSQL连接池"""
    manager = await get_pool_manager()
    return manager.pg_pool


async def get_redis() -> Redis:
    """快捷获取Redis客户端"""
    manager = await get_pool_manager()
    return manager.redis
