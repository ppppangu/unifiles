"""
Redis 缓存实现 - 企业级分布式缓存
适合多实例部署和生产环境

特性：
- 分布式缓存共享
- 高性能连接池
- 自动重连机制
- 健康检查
- 统计信息
- 优雅降级
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed, RedisCache will not be available")


class RedisCache:
    """
    企业级 Redis 缓存实现

    优势：
    - 多实例缓存共享
    - 高可用性（自动重连）
    - 性能优异（连接池）
    - 数据持久化（可选）

    适用场景：
    - 多实例部署
    - 用户数 > 5000
    - QPS > 500
    - 需要缓存共享

    使用方式：
    ```python
    from unifiles.core.cache import get_cache

    cache = get_cache()  # 自动使用 Redis（如果配置了）
    await cache.set("key", "value", ttl_seconds=300)
    value = await cache.get("key")
    ```
    """

    def __init__(self, redis_config: dict):
        """
        初始化 Redis 缓存

        Args:
            redis_config: Redis 配置字典（来自 env_config）
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for RedisCache. "
                "Install it with: pip install redis[asyncio]"
            )

        self.redis_config = redis_config
        self._client: Optional[Redis] = None
        self._is_connected = False
        self._connection_lock = asyncio.Lock()

        # 统计信息
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._last_health_check = None

        # 默认 key 前缀（用于命名空间隔离）
        self._key_prefix = "unifiles:cache:"

    async def _ensure_connected(self) -> bool:
        """
        确保 Redis 连接可用（带自动重连）

        Returns:
            是否连接成功
        """
        if self._client and self._is_connected:
            return True

        async with self._connection_lock:
            # 双重检查
            if self._client and self._is_connected:
                return True

            try:
                # 创建 Redis 客户端
                if "url" in self.redis_config:
                    # 使用 URL 连接
                    self._client = await redis.from_url(
                        self.redis_config["url"],
                        max_connections=self.redis_config.get("max_connections", 50),
                        decode_responses=self.redis_config.get("decode_responses", True),
                        socket_timeout=self.redis_config.get("socket_timeout", 5),
                        socket_connect_timeout=self.redis_config.get("socket_connect_timeout", 5),
                        socket_keepalive=self.redis_config.get("socket_keepalive", True),
                        retry_on_timeout=self.redis_config.get("retry_on_timeout", True),
                        health_check_interval=self.redis_config.get("health_check_interval", 30),
                    )
                else:
                    # 使用主机和端口连接
                    self._client = redis.Redis(
                        host=self.redis_config.get("host", "localhost"),
                        port=self.redis_config.get("port", 6379),
                        db=self.redis_config.get("db", 0),
                        password=self.redis_config.get("password"),
                        max_connections=self.redis_config.get("max_connections", 50),
                        decode_responses=self.redis_config.get("decode_responses", True),
                        socket_timeout=self.redis_config.get("socket_timeout", 5),
                        socket_connect_timeout=self.redis_config.get("socket_connect_timeout", 5),
                        socket_keepalive=self.redis_config.get("socket_keepalive", True),
                        retry_on_timeout=self.redis_config.get("retry_on_timeout", True),
                        health_check_interval=self.redis_config.get("health_check_interval", 30),
                    )

                # 测试连接
                await self._client.ping()
                self._is_connected = True
                logger.info("Redis cache connected successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._is_connected = False
                self._errors += 1
                return False

    def _make_key(self, key: str) -> str:
        """
        生成带前缀的完整 key

        Args:
            key: 原始 key

        Returns:
            带前缀的 key
        """
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期返回 None
        """
        try:
            if not await self._ensure_connected():
                self._misses += 1
                return None

            full_key = self._make_key(key)
            value = await self._client.get(full_key)

            if value is not None:
                self._hits += 1
                # 尝试反序列化 JSON
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # 如果不是 JSON，直接返回字符串
                    return value
            else:
                self._misses += 1
                return None

        except RedisError as e:
            logger.warning(f"Redis get error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in cache.get for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 要缓存的值（支持任何可JSON序列化的对象）
            ttl_seconds: 过期时间（秒），默认5分钟
        """
        try:
            if not await self._ensure_connected():
                return

            full_key = self._make_key(key)

            # 序列化为 JSON（如果不是字符串）
            if isinstance(value, str):
                serialized_value = value
            else:
                serialized_value = json.dumps(value, default=str)

            # 设置值和过期时间
            await self._client.setex(full_key, ttl_seconds, serialized_value)

        except RedisError as e:
            logger.warning(f"Redis set error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in cache.set for key '{key}': {e}")

    async def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        try:
            if not await self._ensure_connected():
                return False

            full_key = self._make_key(key)
            result = await self._client.delete(full_key)
            return result > 0

        except RedisError as e:
            logger.warning(f"Redis delete error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache.delete for key '{key}': {e}")
            return False

    async def clear(self):
        """清空所有缓存（谨慎使用！）"""
        try:
            if not await self._ensure_connected():
                return

            # 只删除带前缀的 key
            pattern = f"{self._key_prefix}*"
            cursor = 0

            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Cleared all cache keys with prefix: {self._key_prefix}")

        except RedisError as e:
            logger.error(f"Redis clear error: {e}")
            self._errors += 1
            self._is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in cache.clear: {e}")

    async def exists(self, key: str) -> bool:
        """
        检查 key 是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        try:
            if not await self._ensure_connected():
                return False

            full_key = self._make_key(key)
            return await self._client.exists(full_key) > 0

        except RedisError as e:
            logger.warning(f"Redis exists error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache.exists for key '{key}': {e}")
            return False

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        """
        设置 key 的过期时间

        Args:
            key: 缓存键
            ttl_seconds: 过期时间（秒）

        Returns:
            是否成功设置
        """
        try:
            if not await self._ensure_connected():
                return False

            full_key = self._make_key(key)
            return await self._client.expire(full_key, ttl_seconds)

        except RedisError as e:
            logger.warning(f"Redis expire error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache.expire for key '{key}': {e}")
            return False

    async def ttl(self, key: str) -> int:
        """
        获取 key 的剩余过期时间

        Args:
            key: 缓存键

        Returns:
            剩余时间（秒），-1表示永不过期，-2表示不存在
        """
        try:
            if not await self._ensure_connected():
                return -2

            full_key = self._make_key(key)
            return await self._client.ttl(full_key)

        except RedisError as e:
            logger.warning(f"Redis ttl error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return -2
        except Exception as e:
            logger.error(f"Unexpected error in cache.ttl for key '{key}': {e}")
            return -2

    async def health_check(self) -> dict:
        """
        健康检查

        Returns:
            健康状态信息
        """
        try:
            if not await self._ensure_connected():
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Not connected to Redis"
                }

            # PING 测试
            start_time = time.time()
            pong = await self._client.ping()
            latency_ms = (time.time() - start_time) * 1000

            # 获取 Redis 信息
            info = await self._client.info()

            self._last_health_check = datetime.now()

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": round(latency_ms, 2),
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
                "last_check": self._last_health_check.isoformat(),
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self._is_connected = False
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_type": "redis",
            "connected": self._is_connected,
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
        }

    async def close(self):
        """关闭 Redis 连接"""
        if self._client:
            try:
                await self._client.close()
                logger.info("Redis cache connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._client = None
                self._is_connected = False

    # ===== 高级功能 =====

    async def incr(self, key: str, amount: int = 1) -> int:
        """
        原子递增

        Args:
            key: 缓存键
            amount: 递增量

        Returns:
            递增后的值
        """
        try:
            if not await self._ensure_connected():
                return 0

            full_key = self._make_key(key)
            return await self._client.incrby(full_key, amount)

        except RedisError as e:
            logger.warning(f"Redis incr error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in cache.incr for key '{key}': {e}")
            return 0

    async def decr(self, key: str, amount: int = 1) -> int:
        """
        原子递减

        Args:
            key: 缓存键
            amount: 递减量

        Returns:
            递减后的值
        """
        try:
            if not await self._ensure_connected():
                return 0

            full_key = self._make_key(key)
            return await self._client.decrby(full_key, amount)

        except RedisError as e:
            logger.warning(f"Redis decr error for key '{key}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in cache.decr for key '{key}': {e}")
            return 0

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        批量获取

        Args:
            keys: 缓存键列表

        Returns:
            键值对字典
        """
        try:
            if not await self._ensure_connected():
                return {}

            full_keys = [self._make_key(k) for k in keys]
            values = await self._client.mget(full_keys)

            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    try:
                        result[keys[i]] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[keys[i]] = value
                    self._hits += 1
                else:
                    self._misses += 1

            return result

        except RedisError as e:
            logger.warning(f"Redis get_many error: {e}")
            self._errors += 1
            self._is_connected = False
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in cache.get_many: {e}")
            return {}

    async def set_many(self, mapping: dict[str, Any], ttl_seconds: int = 300):
        """
        批量设置

        Args:
            mapping: 键值对字典
            ttl_seconds: 过期时间（秒）
        """
        try:
            if not await self._ensure_connected():
                return

            # 使用 pipeline 批量操作
            pipeline = self._client.pipeline()

            for key, value in mapping.items():
                full_key = self._make_key(key)
                if isinstance(value, str):
                    serialized_value = value
                else:
                    serialized_value = json.dumps(value, default=str)

                pipeline.setex(full_key, ttl_seconds, serialized_value)

            await pipeline.execute()

        except RedisError as e:
            logger.warning(f"Redis set_many error: {e}")
            self._errors += 1
            self._is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in cache.set_many: {e}")


# 兼容性：SimpleMemoryCache 的别名（用于优雅降级）
class CacheBackend:
    """缓存后端抽象（用于优雅降级）"""
    pass
