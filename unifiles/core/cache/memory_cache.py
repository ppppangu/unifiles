"""
简单的内存缓存实现 - Redis的临时替代方案
适合单实例部署和早期阶段

当需要扩展时，可以切换到Redis实现
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Optional


class SimpleMemoryCache:
    """
    简单的进程内内存缓存

    优势：
    - 零依赖，立即可用
    - 适合单实例部署
    - 性能极好（纯内存）

    劣势：
    - 多实例时缓存不共享
    - 重启后数据丢失
    - 内存占用需控制

    适用场景：
    - 用户数 < 5000
    - 单实例部署
    - QPS < 500
    """

    def __init__(self, max_size: int = 10000):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数，防止内存溢出
        """
        self._cache: dict[str, Any] = {}
        self._expire: dict[str, datetime] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

        # 统计信息
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期返回None
        """
        async with self._lock:
            if key in self._cache:
                # 检查是否过期
                if datetime.now() < self._expire[key]:
                    self._hits += 1
                    return self._cache[key]
                else:
                    # 过期，删除
                    del self._cache[key]
                    del self._expire[key]
                    self._misses += 1
                    return None

            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 要缓存的值（支持任何可JSON序列化的对象）
            ttl_seconds: 过期时间（秒），默认5分钟
        """
        async with self._lock:
            # 检查缓存大小，如果超过限制，删除最旧的条目
            if len(self._cache) >= self._max_size and key not in self._cache:
                await self._evict_oldest()

            self._cache[key] = value
            self._expire[key] = datetime.now() + timedelta(seconds=ttl_seconds)

    async def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._expire[key]
                return True
            return False

    async def clear(self):
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            self._expire.clear()

    async def cleanup_expired(self):
        """清理过期的缓存条目（定期调用）"""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, expire_time in self._expire.items()
                if now >= expire_time
            ]

            for key in expired_keys:
                del self._cache[key]
                del self._expire[key]

    async def _evict_oldest(self):
        """淘汰最旧的缓存条目（当达到max_size时）"""
        if not self._expire:
            return

        oldest_key = min(self._expire, key=self._expire.get)
        del self._cache[oldest_key]
        del self._expire[oldest_key]

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
        }


# 全局单例缓存实例
_global_cache: Optional[SimpleMemoryCache] = None


def get_cache() -> SimpleMemoryCache:
    """
    获取全局缓存实例（单例模式）

    Returns:
        缓存实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = SimpleMemoryCache(max_size=10000)
    return _global_cache


async def start_cleanup_task():
    """
    启动定期清理任务（在应用启动时调用）

    每5分钟清理一次过期缓存
    """
    cache = get_cache()
    while True:
        await asyncio.sleep(300)  # 5分钟
        await cache.cleanup_expired()


# ===== 使用示例 =====

"""
# 在中间件中使用缓存

from unifiles.core.cache.memory_cache import get_cache

class AuthMiddleware:
    def __init__(self, app):
        self.app = app
        self.cache = get_cache()  # 获取全局缓存实例

    async def _validate_access_key(self, access_key: str, client_ip: str):
        # 构造缓存键
        cache_key = f"token:{access_key}:{client_ip or 'any'}"

        # 先查缓存
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # 缓存未命中，查数据库
        result = await conn.fetchval("SELECT validate_access_key($1, $2)", ...)
        result_dict = json.loads(result)

        # 存入缓存（只缓存有效的token）
        if result_dict.get("valid"):
            await self.cache.set(cache_key, result_dict, ttl_seconds=300)  # 5分钟

        return result_dict


# 在应用启动时启动清理任务

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    cleanup_task = asyncio.create_task(start_cleanup_task())

    yield

    # 关闭时
    cleanup_task.cancel()
"""
