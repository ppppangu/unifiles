"""
数据库连接池管理器
提供统一的数据库连接池管理和配置
"""

from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from loguru import logger

from unifiles.core.config.env_config import read_pg_config


class DatabaseConnectionPool:
    """数据库连接池管理器 - 单例模式"""

    _instance: Optional["DatabaseConnectionPool"] = None
    _pool: Optional[asyncpg.Pool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化连接池配置"""
        if not hasattr(self, "_initialized"):
            self.pg_config = read_pg_config()
            # Filter out non-asyncpg parameters
            self.conn_params = {
                k: v
                for k, v in self.pg_config.items()
                if k in ["host", "port", "user", "password", "database"]
            }
            self._initialized = True

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
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    **self.conn_params,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=command_timeout,
                )
                logger.info(
                    f"Database connection pool initialized: min={min_size}, max={max_size}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")

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
                logger.error(f"Database operation error: {e}")
                raise

    async def get_connection(self) -> asyncpg.Connection:
        """
        获取单个数据库连接（用于向后兼容）

        Returns:
            asyncpg.Connection: 数据库连接
        """
        return await asyncpg.connect(**self.conn_params)

    @property
    def is_initialized(self) -> bool:
        """检查连接池是否已初始化"""
        return self._pool is not None


# 全局连接池实例
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
