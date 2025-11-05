"""
缓存模块 - 提供灵活的缓存抽象

支持：
- SimpleMemoryCache: 进程内内存缓存（默认，适合单实例）
- RedisCache: 分布式缓存（可选，适合多实例）

使用方式：
from unifiles.core.cache import get_cache

cache = get_cache()
await cache.set("key", "value", ttl_seconds=300)
value = await cache.get("key")

自动选择：
- 如果配置了 UNIFILES_REDIS_URL，自动使用 RedisCache
- 否则使用 SimpleMemoryCache（单实例部署）
"""

from typing import Union, Optional
from loguru import logger

from unifiles.core.cache.memory_cache import SimpleMemoryCache, start_cleanup_task

# 尝试导入 RedisCache（如果 redis 包未安装，将回退到 SimpleMemoryCache）
try:
    from unifiles.core.cache.redis_cache import RedisCache
    REDIS_CACHE_AVAILABLE = True
except ImportError:
    REDIS_CACHE_AVAILABLE = False
    logger.info("RedisCache not available, using SimpleMemoryCache")


# 全局缓存实例
_global_cache: Optional[Union[SimpleMemoryCache, "RedisCache"]] = None
_cache_type: str = "memory"  # "memory" or "redis"


def get_cache(force_type: Optional[str] = None) -> Union[SimpleMemoryCache, "RedisCache"]:
    """
    获取全局缓存实例（单例模式）

    自动选择策略：
    1. 如果配置了 UNIFILES_REDIS_URL 且 redis 包可用 → RedisCache
    2. 否则 → SimpleMemoryCache

    Args:
        force_type: 强制使用特定类型 ("memory" 或 "redis")，用于测试

    Returns:
        缓存实例

    Examples:
        # 自动选择
        cache = get_cache()

        # 强制使用内存缓存
        cache = get_cache(force_type="memory")

        # 强制使用 Redis 缓存
        cache = get_cache(force_type="redis")
    """
    global _global_cache, _cache_type

    if _global_cache is not None:
        return _global_cache

    # 确定使用哪种缓存
    use_redis = False

    if force_type == "redis":
        use_redis = True
    elif force_type == "memory":
        use_redis = False
    else:
        # 自动检测
        try:
            from unifiles.config import settings

            # 如果配置了 Redis
            if settings.redis.host:
                if REDIS_CACHE_AVAILABLE:
                    use_redis = True
                    logger.info("Redis configuration detected, using RedisCache")
                else:
                    logger.warning(
                        "Redis configuration detected but redis package not installed. "
                        "Install with: pip install redis[asyncio]. Falling back to SimpleMemoryCache."
                    )
        except Exception as e:
            logger.warning(f"Failed to read Redis config: {e}. Using SimpleMemoryCache.")

    # 创建缓存实例
    if use_redis and REDIS_CACHE_AVAILABLE:
        try:
            from unifiles.config import settings

            # 构建 Redis 配置字典
            redis_config = {
                "host": settings.redis.host,
                "port": settings.redis.port,
                "db": settings.redis.db,
                "password": settings.redis.password,
                "max_connections": settings.redis.max_connections,
                "decode_responses": True,
                "encoding": "utf-8",
                "socket_timeout": settings.redis.socket_timeout,
                "socket_connect_timeout": settings.redis.socket_connect_timeout,
            }
            _global_cache = RedisCache(redis_config)
            _cache_type = "redis"
            logger.info("Initialized RedisCache for distributed caching")
        except Exception as e:
            logger.error(f"Failed to initialize RedisCache: {e}. Falling back to SimpleMemoryCache.")
            _global_cache = SimpleMemoryCache(max_size=10000)
            _cache_type = "memory"
    else:
        _global_cache = SimpleMemoryCache(max_size=10000)
        _cache_type = "memory"
        logger.info("Initialized SimpleMemoryCache for single-instance caching")

    return _global_cache


def get_cache_type() -> str:
    """
    获取当前使用的缓存类型

    Returns:
        "memory" 或 "redis"
    """
    return _cache_type


async def close_cache():
    """
    关闭缓存连接（应用关闭时调用）

    对于 RedisCache，会关闭 Redis 连接
    对于 SimpleMemoryCache，会清空缓存
    """
    global _global_cache

    if _global_cache is not None:
        if hasattr(_global_cache, "close"):
            await _global_cache.close()
        else:
            await _global_cache.clear()

        logger.info(f"Cache ({_cache_type}) closed")
        _global_cache = None


__all__ = [
    "SimpleMemoryCache",
    "RedisCache" if REDIS_CACHE_AVAILABLE else None,
    "get_cache",
    "get_cache_type",
    "close_cache",
    "start_cleanup_task",
]

# 移除 None 值
__all__ = [item for item in __all__ if item is not None]
