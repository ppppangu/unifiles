"""
数据库连接池管理器
提供统一的数据库连接池管理和配置
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

from unifiles.core.config.env_config import read_pg_config
from unifiles.core.logging import get_logger


def _get_logger():
    """延迟获取 logger，避免在模块 import 时过早初始化"""
    return get_logger()


class DatabaseConnectionPool:
    """数据库连接池管理器"""

    def __init__(self):
        """初始化连接池配置"""
        self._pool: Optional[asyncpg.Pool] = None
        self._init_lock = asyncio.Lock()
        self._pg_config = None
        self._conn_params = None

    def _ensure_config(self):
        """延迟加载配置"""
        if self._pg_config is None:
            self._pg_config = read_pg_config()
            self._conn_params = {
                k: v
                for k, v in self._pg_config.items()
                if k in ["host", "port", "user", "password", "database"]
            }

    async def initialize(
        self, min_size: int = 5, max_size: int = 20, command_timeout: float = 30.0
    ):
        """
        初始化连接池

        Args:
            min_size: 最小连接数
            max_size: 最大连接数
            command_timeout: 命令超时时间（秒）
        """
        if self._pool is not None:
            return

        async with self._init_lock:
            if self._pool is not None:
                return
            try:
                self._ensure_config()
                self._pool = await asyncpg.create_pool(
                    **self._conn_params,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=command_timeout,
                )
                _get_logger().info(
                    f"Database connection pool initialized: min={min_size}, max={max_size}"
                )
            except Exception as e:
                _get_logger().error(f"Failed to initialize connection pool: {e}")
                raise

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            _get_logger().info("Database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """
        获取数据库连接

        Yields:
            asyncpg.Connection: 数据库连接
        """
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                _get_logger().error(f"Database operation error: {e}")
                raise

    async def get_connection(self) -> asyncpg.Connection:
        """
        获取单个数据库连接（已弃用，推荐使用 acquire() 方法）

        .. deprecated::
            此方法已弃用，请使用 `acquire()` 上下文管理器来获取连接。
            此方法现在通过连接池获取连接，但调用者需要负责释放连接。

        Returns:
            asyncpg.Connection: 数据库连接（需要手动释放）
        """
        import warnings

        warnings.warn(
            "get_connection() is deprecated, use acquire() context manager instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._pool:
            await self.initialize()
        return await self._pool.acquire()

    @property
    def is_initialized(self) -> bool:
        """检查连接池是否已初始化"""
        return self._pool is not None


# 模块级单例实例
_connection_pool = DatabaseConnectionPool()


async def get_connection_pool() -> DatabaseConnectionPool:
    """
    获取全局连接池实例

    Returns:
        DatabaseConnectionPool: 连接池实例
    """
    if not _connection_pool.is_initialized:
        await _connection_pool.initialize()
    return _connection_pool


async def initialize_connection_pool(
    min_size: int = 5, max_size: int = 20, command_timeout: float = 30.0
):
    """
    初始化全局连接池

    Args:
        min_size: 最小连接数
        max_size: 最大连接数
        command_timeout: 命令超时时间（秒）
    """
    await _connection_pool.initialize(min_size, max_size, command_timeout)


async def close_connection_pool():
    """关闭全局连接池"""
    await _connection_pool.close()
