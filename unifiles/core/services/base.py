"""
服务基类 - 统一服务的初始化和资源管理模式

所有业务服务都应该继承此类，统一：
- 初始化流程（initialize方法）
- 资源清理（cleanup方法）
- 连接池访问
"""

from abc import ABC, abstractmethod
from loguru import logger

from unifiles.core.database.pool_manager import get_pool_manager


class BaseService(ABC):
    """
    服务基类

    所有业务服务都应该继承此类

    使用示例：
    ```python
    class MyService(BaseService):
        async def _setup(self):
            # 初始化逻辑
            self.my_resource = await create_resource()

        async def _teardown(self):
            # 清理逻辑
            await self.my_resource.close()

        async def do_something(self):
            # 确保已初始化
            self.ensure_initialized()

            # 使用共享连接池
            async with self.pg_pool.acquire() as conn:
                result = await conn.fetch("SELECT ...")

            return result

    # 使用
    service = MyService()
    await service.initialize()
    result = await service.do_something()
    await service.cleanup()
    ```
    """

    def __init__(self):
        self._initialized = False
        self._pool_manager = None

    async def initialize(self):
        """
        初始化服务（幂等操作）

        此方法会：
        1. 获取全局连接池管理器
        2. 调用子类的_setup方法
        """
        if self._initialized:
            logger.debug(f"{self.__class__.__name__} already initialized")
            return

        logger.info(f"Initializing {self.__class__.__name__}...")

        # 获取连接池管理器
        self._pool_manager = await get_pool_manager()

        # 调用子类初始化逻辑
        await self._setup()

        self._initialized = True
        logger.success(f"{self.__class__.__name__} initialized")

    @abstractmethod
    async def _setup(self):
        """
        子类实现具体的初始化逻辑

        在此方法中：
        - 创建特定的资源
        - 初始化内部状态
        - 建立必要的连接（除了PG和Redis，这些由pool_manager管理）
        """
        pass

    async def cleanup(self):
        """
        清理服务资源

        此方法会：
        1. 调用子类的_teardown方法
        2. 重置初始化状态
        """
        if not self._initialized:
            return

        logger.info(f"Cleaning up {self.__class__.__name__}...")

        # 调用子类清理逻辑
        await self._teardown()

        self._initialized = False
        logger.success(f"{self.__class__.__name__} cleaned up")

    @abstractmethod
    async def _teardown(self):
        """
        子类实现具体的清理逻辑

        在此方法中：
        - 关闭打开的资源
        - 清理内部状态
        """
        pass

    @property
    def pg_pool(self):
        """获取PostgreSQL连接池"""
        if not self._pool_manager:
            raise RuntimeError(
                f"{self.__class__.__name__} not initialized, call initialize() first"
            )
        return self._pool_manager.pg_pool

    @property
    def redis(self):
        """获取Redis客户端"""
        if not self._pool_manager:
            raise RuntimeError(
                f"{self.__class__.__name__} not initialized, call initialize() first"
            )
        return self._pool_manager.redis

    @property
    def is_initialized(self) -> bool:
        """检查服务是否已初始化"""
        return self._initialized

    def ensure_initialized(self):
        """确保服务已初始化，否则抛出异常"""
        if not self._initialized:
            raise RuntimeError(
                f"{self.__class__.__name__} not initialized, call initialize() first"
            )
