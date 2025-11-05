"""
Redis 队列客户端封装 - 企业级消息队列实现

提供：
- 任务队列操作（FIFO、优先级队列）
- Pub/Sub 实时事件发布
- 信号量控制（并发限制）
- 任务状态管理
- 健康检查和统计

特性：
- 自动重连机制
- 完整的错误处理
- 性能优化（批量操作、Pipeline）
- 详细的日志记录
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator

from loguru import logger

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis, PubSub
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed, RedisQueueClient will not be available")
    # Fallback type definitions
    Redis = Any  # type: ignore
    PubSub = Any  # type: ignore
    RedisError = Exception  # type: ignore
    RedisConnectionError = Exception  # type: ignore

from unifiles.core.queue.constants import (
    QueueNames,
    EventChannels,
    TaskStatus,
    RedisKeyPrefixes,
)


class RedisQueueClient:
    """
    企业级 Redis 队列客户端

    功能：
    1. 任务队列操作（enqueue、dequeue）
    2. 优先级队列（Sorted Set）
    3. Pub/Sub 事件发布和订阅
    4. 信号量控制（并发限制）
    5. 任务状态管理（带 TTL）
    6. 批量操作优化

    使用示例：
    ```python
    from unifiles.core.queue import get_queue_client

    queue = get_queue_client()

    # 入队任务
    await queue.enqueue(QueueNames.FILE_UPLOAD, {
        "task_id": "task_123",
        "file_id": "file_456",
        "user_id": "user_789"
    })

    # 出队任务（阻塞）
    task = await queue.dequeue(QueueNames.FILE_UPLOAD, timeout=10)

    # 发布事件
    await queue.publish(EventChannels.FILE_UPLOADS, {
        "event": "file_uploaded",
        "file_id": "file_456"
    })

    # 设置任务状态
    await queue.set_task_status("task_123", {
        "status": "processing",
        "progress": 50
    })
    ```
    """

    def __init__(self, redis_config: dict):
        """
        初始化 Redis 队列客户端

        Args:
            redis_config: Redis 配置字典（来自 env_config）
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for RedisQueueClient. "
                "Install it with: pip install redis[asyncio]"
            )

        self.redis_config = redis_config
        self._client: Optional[Redis] = None
        self._is_connected = False
        self._connection_lock = asyncio.Lock()

        # 统计信息
        self._enqueue_count = 0
        self._dequeue_count = 0
        self._publish_count = 0
        self._errors = 0

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
                    self._client = await redis.from_url(
                        self.redis_config["url"],
                        max_connections=self.redis_config.get("max_connections", 50),
                        decode_responses=False,  # 队列需要处理二进制数据
                        socket_timeout=self.redis_config.get("socket_timeout", 5),
                        socket_connect_timeout=self.redis_config.get("socket_connect_timeout", 5),
                        socket_keepalive=self.redis_config.get("socket_keepalive", True),
                        retry_on_timeout=self.redis_config.get("retry_on_timeout", True),
                        health_check_interval=self.redis_config.get("health_check_interval", 30),
                    )
                else:
                    self._client = redis.Redis(
                        host=self.redis_config.get("host", "localhost"),
                        port=self.redis_config.get("port", 6379),
                        db=self.redis_config.get("db", 0),
                        password=self.redis_config.get("password"),
                        max_connections=self.redis_config.get("max_connections", 50),
                        decode_responses=False,  # 队列需要处理二进制数据
                        socket_timeout=self.redis_config.get("socket_timeout", 5),
                        socket_connect_timeout=self.redis_config.get("socket_connect_timeout", 5),
                        socket_keepalive=self.redis_config.get("socket_keepalive", True),
                        retry_on_timeout=self.redis_config.get("retry_on_timeout", True),
                        health_check_interval=self.redis_config.get("health_check_interval", 30),
                    )

                # 测试连接
                await self._client.ping()
                self._is_connected = True
                logger.info("Redis queue client connected successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._is_connected = False
                self._errors += 1
                return False

    # ===== 队列操作 =====

    async def enqueue(self, queue_name: str, task: dict, to_front: bool = False) -> bool:
        """
        将任务加入队列

        Args:
            queue_name: 队列名称（使用 QueueNames 常量）
            task: 任务数据（字典）
            to_front: 是否加入队列头部（紧急任务）

        Returns:
            是否成功加入队列
        """
        try:
            if not await self._ensure_connected():
                return False

            task_json = json.dumps(task, default=str).encode('utf-8')

            if to_front:
                # 加入队列头部（右侧推入）
                await self._client.rpush(queue_name, task_json)
            else:
                # 加入队列尾部（左侧推入）
                await self._client.lpush(queue_name, task_json)

            self._enqueue_count += 1
            logger.debug(f"Task enqueued to {queue_name}: {task.get('task_id')}")
            return True

        except RedisError as e:
            logger.error(f"Redis enqueue error for queue '{queue_name}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in enqueue: {e}")
            return False

    async def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """
        从队列取出任务（阻塞）

        Args:
            queue_name: 队列名称
            timeout: 超时时间（秒），0 表示无限等待

        Returns:
            任务数据字典，如果超时返回 None
        """
        try:
            if not await self._ensure_connected():
                return None

            # BRPOP 从队列尾部弹出（FIFO）
            result = await self._client.brpop(queue_name, timeout=timeout)

            if result:
                _, task_json = result
                task = json.loads(task_json.decode('utf-8'))
                self._dequeue_count += 1
                logger.debug(f"Task dequeued from {queue_name}: {task.get('task_id')}")
                return task
            else:
                # 超时，没有任务
                return None

        except RedisError as e:
            logger.error(f"Redis dequeue error for queue '{queue_name}': {e}")
            self._errors += 1
            self._is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in dequeue: {e}")
            return None

    async def enqueue_priority(self, queue_name: str, task: dict, priority: int) -> bool:
        """
        将任务加入优先级队列（使用 Sorted Set）

        Args:
            queue_name: 队列名称
            task: 任务数据
            priority: 优先级（数值越大越优先，使用 TaskPriority 常量）

        Returns:
            是否成功加入队列
        """
        try:
            if not await self._ensure_connected():
                return False

            # 计算 score：优先级越高，score 越小（先被处理）
            # 同时加入时间戳确保同优先级按 FIFO
            score = -priority * 1000000 + time.time()

            task_json = json.dumps(task, default=str).encode('utf-8')
            await self._client.zadd(queue_name, {task_json: score})

            self._enqueue_count += 1
            logger.debug(
                f"Task enqueued to priority queue {queue_name} "
                f"with priority {priority}: {task.get('task_id')}"
            )
            return True

        except RedisError as e:
            logger.error(f"Redis enqueue_priority error for queue '{queue_name}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in enqueue_priority: {e}")
            return False

    async def dequeue_priority(self, queue_name: str) -> Optional[dict]:
        """
        从优先级队列取出任务（非阻塞）

        Args:
            queue_name: 队列名称

        Returns:
            任务数据字典，如果队列为空返回 None
        """
        try:
            if not await self._ensure_connected():
                return None

            # ZPOPMIN 弹出 score 最小的元素（最高优先级）
            result = await self._client.zpopmin(queue_name)

            if result:
                task_json, score = result[0]
                task = json.loads(task_json.decode('utf-8'))
                self._dequeue_count += 1
                logger.debug(f"Task dequeued from priority queue {queue_name}: {task.get('task_id')}")
                return task
            else:
                return None

        except RedisError as e:
            logger.error(f"Redis dequeue_priority error for queue '{queue_name}': {e}")
            self._errors += 1
            self._is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in dequeue_priority: {e}")
            return None

    async def get_queue_length(self, queue_name: str, is_priority: bool = False) -> int:
        """
        获取队列长度

        Args:
            queue_name: 队列名称
            is_priority: 是否为优先级队列

        Returns:
            队列中的任务数量
        """
        try:
            if not await self._ensure_connected():
                return 0

            if is_priority:
                # Sorted Set 使用 ZCARD
                return await self._client.zcard(queue_name)
            else:
                # List 使用 LLEN
                return await self._client.llen(queue_name)

        except RedisError as e:
            logger.warning(f"Redis get_queue_length error for queue '{queue_name}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in get_queue_length: {e}")
            return 0

    # ===== Pub/Sub 操作 =====

    async def publish(self, channel: str, message: dict) -> int:
        """
        发布消息到 Pub/Sub 频道

        Args:
            channel: 频道名称（使用 EventChannels 常量）
            message: 消息数据（字典）

        Returns:
            接收到消息的订阅者数量
        """
        try:
            if not await self._ensure_connected():
                return 0

            message_json = json.dumps(message, default=str)
            subscribers = await self._client.publish(channel, message_json)

            self._publish_count += 1
            logger.debug(f"Message published to {channel}, {subscribers} subscribers")
            return subscribers

        except RedisError as e:
            logger.error(f"Redis publish error for channel '{channel}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in publish: {e}")
            return 0

    async def subscribe(self, *channels: str) -> Optional[PubSub]:
        """
        订阅 Pub/Sub 频道

        Args:
            *channels: 要订阅的频道名称列表

        Returns:
            PubSub 对象，可以用于接收消息
        """
        try:
            if not await self._ensure_connected():
                return None

            pubsub = self._client.pubsub()
            await pubsub.subscribe(*channels)

            logger.info(f"Subscribed to channels: {', '.join(channels)}")
            return pubsub

        except RedisError as e:
            logger.error(f"Redis subscribe error: {e}")
            self._errors += 1
            self._is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in subscribe: {e}")
            return None

    async def listen_messages(self, pubsub: PubSub) -> AsyncGenerator[dict, None]:
        """
        监听 Pub/Sub 消息（异步生成器）

        Args:
            pubsub: PubSub 对象

        Yields:
            消息字典
        """
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"].decode('utf-8'))
                        yield data
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning(f"Failed to decode message: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error in listen_messages: {e}")
            raise

    # ===== 信号量操作（并发控制） =====

    async def semaphore_acquire(self, resource: str, max_count: int, timeout: int = 30) -> bool:
        """
        获取信号量（用于并发控制）

        Args:
            resource: 资源名称（使用 SemaphoreKeys 常量）
            max_count: 最大并发数
            timeout: 超时时间（秒）

        Returns:
            是否成功获取
        """
        try:
            if not await self._ensure_connected():
                return False

            start_time = time.time()

            while True:
                current = await self._client.incr(resource)

                if current <= max_count:
                    # 成功获取
                    logger.debug(f"Semaphore acquired for {resource}: {current}/{max_count}")
                    return True
                else:
                    # 超出限制，回退
                    await self._client.decr(resource)

                    if time.time() - start_time > timeout:
                        logger.warning(f"Semaphore acquire timeout for {resource}")
                        return False

                    # 等待 1 秒后重试
                    await asyncio.sleep(1)

        except RedisError as e:
            logger.error(f"Redis semaphore_acquire error for resource '{resource}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in semaphore_acquire: {e}")
            return False

    async def semaphore_release(self, resource: str) -> int:
        """
        释放信号量

        Args:
            resource: 资源名称

        Returns:
            释放后的当前值
        """
        try:
            if not await self._ensure_connected():
                return 0

            current = await self._client.decr(resource)
            logger.debug(f"Semaphore released for {resource}: {current}")
            return max(0, current)  # 确保不为负数

        except RedisError as e:
            logger.error(f"Redis semaphore_release error for resource '{resource}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in semaphore_release: {e}")
            return 0

    async def semaphore_get(self, resource: str) -> int:
        """
        获取当前信号量值

        Args:
            resource: 资源名称

        Returns:
            当前信号量值
        """
        try:
            if not await self._ensure_connected():
                return 0

            value = await self._client.get(resource)
            return int(value) if value else 0

        except RedisError as e:
            logger.warning(f"Redis semaphore_get error for resource '{resource}': {e}")
            self._errors += 1
            self._is_connected = False
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in semaphore_get: {e}")
            return 0

    # ===== 任务状态管理 =====

    async def set_task_status(self, task_id: str, status: dict, ttl: int = 86400):
        """
        设置任务状态（带 TTL，24 小时后自动过期）

        Args:
            task_id: 任务 ID
            status: 状态数据（字典）
            ttl: 过期时间（秒），默认 24 小时
        """
        try:
            if not await self._ensure_connected():
                return

            key = f"{RedisKeyPrefixes.TASK_STATUS}{task_id}"
            status_json = json.dumps(status, default=str)

            await self._client.setex(key, ttl, status_json)
            logger.debug(f"Task status set for {task_id}: {status.get('status')}")

        except RedisError as e:
            logger.error(f"Redis set_task_status error for task '{task_id}': {e}")
            self._errors += 1
            self._is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in set_task_status: {e}")

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            状态数据字典，如果不存在返回 None
        """
        try:
            if not await self._ensure_connected():
                return None

            key = f"{RedisKeyPrefixes.TASK_STATUS}{task_id}"
            status_json = await self._client.get(key)

            if status_json:
                return json.loads(status_json.decode('utf-8'))
            else:
                return None

        except RedisError as e:
            logger.warning(f"Redis get_task_status error for task '{task_id}': {e}")
            self._errors += 1
            self._is_connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_task_status: {e}")
            return None

    async def delete_task_status(self, task_id: str) -> bool:
        """
        删除任务状态

        Args:
            task_id: 任务 ID

        Returns:
            是否成功删除
        """
        try:
            if not await self._ensure_connected():
                return False

            key = f"{RedisKeyPrefixes.TASK_STATUS}{task_id}"
            result = await self._client.delete(key)
            return result > 0

        except RedisError as e:
            logger.warning(f"Redis delete_task_status error for task '{task_id}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in delete_task_status: {e}")
            return False

    # ===== 任务锁（防止重复处理） =====

    async def acquire_task_lock(self, task_id: str, ttl: int = 300) -> bool:
        """
        获取任务锁（防止重复处理）

        Args:
            task_id: 任务 ID
            ttl: 锁过期时间（秒），默认 5 分钟

        Returns:
            是否成功获取锁
        """
        try:
            if not await self._ensure_connected():
                return False

            key = f"{RedisKeyPrefixes.TASK_LOCK}{task_id}"
            # SETNX：只有当 key 不存在时才设置
            result = await self._client.set(key, "locked", ex=ttl, nx=True)

            if result:
                logger.debug(f"Task lock acquired for {task_id}")
                return True
            else:
                logger.warning(f"Task lock already exists for {task_id}")
                return False

        except RedisError as e:
            logger.error(f"Redis acquire_task_lock error for task '{task_id}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in acquire_task_lock: {e}")
            return False

    async def release_task_lock(self, task_id: str) -> bool:
        """
        释放任务锁

        Args:
            task_id: 任务 ID

        Returns:
            是否成功释放
        """
        try:
            if not await self._ensure_connected():
                return False

            key = f"{RedisKeyPrefixes.TASK_LOCK}{task_id}"
            result = await self._client.delete(key)
            logger.debug(f"Task lock released for {task_id}")
            return result > 0

        except RedisError as e:
            logger.error(f"Redis release_task_lock error for task '{task_id}': {e}")
            self._errors += 1
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error in release_task_lock: {e}")
            return False

    # ===== 健康检查和统计 =====

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
            await self._client.ping()
            latency_ms = (time.time() - start_time) * 1000

            # 获取 Redis 信息
            info = await self._client.info()

            # 获取队列长度
            queue_lengths = {}
            for queue_name in [
                QueueNames.FILE_UPLOAD,
                QueueNames.FILE_PROCESS,
                QueueNames.WEBHOOK_DISPATCH,
            ]:
                try:
                    length = await self.get_queue_length(queue_name)
                    queue_lengths[queue_name] = length
                except Exception:
                    pass

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": round(latency_ms, 2),
                "redis_version": info.get("redis_version"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
                "queue_lengths": queue_lengths,
                "stats": self.get_stats(),
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
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "enqueue_count": self._enqueue_count,
            "dequeue_count": self._dequeue_count,
            "publish_count": self._publish_count,
            "errors": self._errors,
            "connected": self._is_connected,
        }

    async def close(self):
        """关闭 Redis 连接"""
        if self._client:
            try:
                await self._client.close()
                logger.info("Redis queue client connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._client = None
                self._is_connected = False


# ===== 全局单例 =====

_global_queue_client: Optional[RedisQueueClient] = None


def get_queue_client() -> RedisQueueClient:
    """
    获取全局队列客户端实例（单例模式）

    Returns:
        RedisQueueClient 实例
    """
    global _global_queue_client

    if _global_queue_client is None:
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
        _global_queue_client = RedisQueueClient(redis_config)
        logger.info("Global queue client initialized")

    return _global_queue_client


async def close_queue_client():
    """
    关闭全局队列客户端（应用关闭时调用）
    """
    global _global_queue_client

    if _global_queue_client is not None:
        await _global_queue_client.close()
        _global_queue_client = None
        logger.info("Global queue client closed")
# Add alias for backward compatibility
get_queue_service = get_queue_client
