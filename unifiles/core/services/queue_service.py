"""
队列服务 - Redis 队列操作的高级封装

功能：
- 任务入队（自动创建任务记录）
- 任务出队（自动更新状态）
- 事件发布
- 队列监控

集成 TaskService 和 RedisQueueClient，提供一站式队列管理
"""

from typing import Any, Dict, Optional
from datetime import datetime

from loguru import logger

from unifiles.core.queue import (
    RedisQueueClient,
    get_queue_client,
    QueueNames,
    EventChannels,
    TaskTypes,
    TaskStatus,
    TaskPriority,
)
from unifiles.core.services.task_service import TaskService


class QueueService:
    """
    队列服务 - 集成任务管理和队列操作

    提供：
    - 创建任务并入队（一次调用完成）
    - 从队列取出任务（自动更新状态）
    - 发布事件到 Pub/Sub
    - 队列健康检查

    使用示例：
    ```python
    queue_service = QueueService()
    await queue_service.init()

    # 创建任务并入队
    task = await queue_service.enqueue_task(
        user_id="user_123",
        queue_name=QueueNames.FILE_UPLOAD,
        task_type=TaskTypes.FILE_UPLOAD,
        task_data={"file_id": "file_456"},
        priority=TaskPriority.HIGH
    )

    # Worker 从队列取出任务
    task = await queue_service.dequeue_task(QueueNames.FILE_UPLOAD)

    # 发布事件
    await queue_service.publish_event(
        EventChannels.FILE_UPLOADS,
        {"event": "file_uploaded", "file_id": "file_456"}
    )
    ```
    """

    def __init__(
        self,
        queue_client: Optional[RedisQueueClient] = None,
        task_service: Optional[TaskService] = None,
    ):
        """
        初始化队列服务

        Args:
            queue_client: Redis 队列客户端（可选，默认使用全局单例）
            task_service: 任务服务（可选，默认创建新实例）
        """
        self.queue_client = queue_client or get_queue_client()
        self.task_service = task_service or TaskService()

    async def init(self):
        """初始化服务（连接池等）"""
        await self.task_service.init_pool()
        logger.info("QueueService initialized")

    async def close(self):
        """关闭服务"""
        await self.task_service.close_pool()
        logger.info("QueueService closed")

    # ===== 任务入队 =====

    async def enqueue_task(
        self,
        user_id: str,
        queue_name: str,
        task_type: str,
        task_data: Dict[str, Any],
        file_id: Optional[str] = None,
        priority: int = TaskPriority.NORMAL,
        use_priority_queue: bool = False,
        related_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        创建任务并加入队列（一次调用完成）

        Args:
            user_id: 用户 ID
            queue_name: 队列名称（使用 QueueNames 常量）
            task_type: 任务类型（使用 TaskTypes 常量）
            task_data: 任务数据
            file_id: 关联文件 ID
            priority: 优先级（0-100）
            use_priority_queue: 是否使用优先级队列
            related_task_id: 关联的父任务 ID
            metadata: 额外的元数据

        Returns:
            任务信息（包含 task_id）

        Raises:
            Exception: 创建或入队失败时抛出
        """
        try:
            # 1. 创建任务记录到数据库
            task = await self.task_service.create_task(
                user_id=user_id,
                task_type=task_type,
                task_data=task_data,
                file_id=file_id,
                priority=priority,
                related_task_id=related_task_id,
                metadata=metadata,
            )

            task_id = task["task_id"]

            # 2. 构建队列任务数据
            queue_task = {
                "task_id": task_id,
                "user_id": user_id,
                "task_type": task_type,
                "file_id": file_id,
                "task_data": task_data,
                "priority": priority,
                "created_at": task["created_at"],
            }

            # 3. 加入队列
            if use_priority_queue:
                # 使用优先级队列
                success = await self.queue_client.enqueue_priority(
                    queue_name, queue_task, priority
                )
            else:
                # 使用普通队列（FIFO）
                success = await self.queue_client.enqueue(queue_name, queue_task)

            if not success:
                logger.error(f"Failed to enqueue task {task_id} to {queue_name}")
                raise Exception(f"Failed to enqueue task to {queue_name}")

            logger.info(
                f"Task {task_id} created and enqueued to {queue_name} "
                f"(priority: {priority}, type: {task_type})"
            )

            return task

        except Exception as e:
            logger.error(f"Error in enqueue_task: {e}")
            raise

    # ===== 任务出队 =====

    async def dequeue_task(
        self,
        queue_name: str,
        timeout: int = 10,
        from_priority_queue: bool = False,
        worker_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        从队列取出任务（自动更新状态为 processing）

        Args:
            queue_name: 队列名称
            timeout: 超时时间（秒），仅用于普通队列
            from_priority_queue: 是否从优先级队列取出
            worker_id: Worker ID（用于记录）

        Returns:
            任务数据，如果队列为空返回 None
        """
        try:
            # 1. 从队列取出任务
            if from_priority_queue:
                task = await self.queue_client.dequeue_priority(queue_name)
            else:
                task = await self.queue_client.dequeue(queue_name, timeout=timeout)

            if not task:
                return None

            task_id = task.get("task_id")

            # 2. 尝试获取任务锁（防止重复处理）
            if task_id:
                lock_acquired = await self.queue_client.acquire_task_lock(
                    task_id, ttl=300
                )
                if not lock_acquired:
                    logger.warning(
                        f"Task {task_id} already locked by another worker, skipping"
                    )
                    return None

                # 3. 更新任务状态为 processing
                await self.task_service.update_status(
                    task_id=task_id,
                    status=TaskStatus.PROCESSING,
                    worker_id=worker_id,
                )

                logger.info(
                    f"Task {task_id} dequeued from {queue_name} "
                    f"(worker: {worker_id or 'unknown'})"
                )

            return task

        except Exception as e:
            logger.error(f"Error in dequeue_task from {queue_name}: {e}")
            return None

    # ===== 任务完成/失败 =====

    async def complete_task(
        self,
        task_id: str,
        result_data: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        标记任务为完成（同时释放锁）

        Args:
            task_id: 任务 ID
            result_data: 结果数据
            worker_id: Worker ID

        Returns:
            是否成功
        """
        try:
            # 1. 更新任务状态
            await self.task_service.update_status(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                progress=100,
                result_data=result_data,
                worker_id=worker_id,
            )

            # 2. 释放任务锁
            await self.queue_client.release_task_lock(task_id)

            logger.info(f"Task {task_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return False

    async def fail_task(
        self,
        task_id: str,
        error_data: Dict[str, Any],
        worker_id: Optional[str] = None,
    ) -> bool:
        """
        标记任务为失败（同时释放锁）

        Args:
            task_id: 任务 ID
            error_data: 错误信息
            worker_id: Worker ID

        Returns:
            是否成功
        """
        try:
            # 1. 更新任务状态
            await self.task_service.update_status(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_data=error_data,
                worker_id=worker_id,
            )

            # 2. 释放任务锁
            await self.queue_client.release_task_lock(task_id)

            logger.warning(f"Task {task_id} failed: {error_data.get('error')}")
            return True

        except Exception as e:
            logger.error(f"Error failing task {task_id}: {e}")
            return False

    # ===== 事件发布 =====

    async def publish_event(
        self, channel: str, event_data: Dict[str, Any]
    ) -> int:
        """
        发布事件到 Pub/Sub 频道

        Args:
            channel: 频道名称（使用 EventChannels 常量）
            event_data: 事件数据

        Returns:
            接收到事件的订阅者数量
        """
        try:
            # 添加时间戳
            event_data["timestamp"] = datetime.now().isoformat()

            subscribers = await self.queue_client.publish(channel, event_data)

            logger.debug(
                f"Event published to {channel}, {subscribers} subscribers notified"
            )
            return subscribers

        except Exception as e:
            logger.error(f"Error publishing event to {channel}: {e}")
            return 0

    # ===== 监控和统计 =====

    async def get_queue_lengths(self) -> Dict[str, int]:
        """
        获取所有队列的长度

        Returns:
            队列长度字典 {queue_name: length}
        """
        try:
            queue_lengths = {}

            # 检查所有定义的队列
            for queue_name in [
                QueueNames.FILE_UPLOAD,
                QueueNames.FILE_PROCESS,
                QueueNames.FILE_PROCESS_PRIORITY,
                QueueNames.WEBHOOK_DISPATCH,
                QueueNames.NOTIFICATION,
                QueueNames.BACKGROUND_TASK,
            ]:
                try:
                    length = await self.queue_client.get_queue_length(queue_name)
                    queue_lengths[queue_name] = length
                except Exception as e:
                    logger.warning(f"Failed to get length for {queue_name}: {e}")
                    queue_lengths[queue_name] = -1

            return queue_lengths

        except Exception as e:
            logger.error(f"Error getting queue lengths: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """
        队列服务健康检查

        Returns:
            健康状态信息
        """
        try:
            # 1. Redis 队列健康检查
            redis_health = await self.queue_client.health_check()

            # 2. 获取队列长度
            queue_lengths = await self.get_queue_lengths()

            # 3. 检查是否有积压（超过 1000 个任务视为积压）
            backlog_warning = any(
                length > 1000 for length in queue_lengths.values() if length > 0
            )

            return {
                "status": "healthy" if redis_health.get("connected") else "unhealthy",
                "redis": redis_health,
                "queue_lengths": queue_lengths,
                "backlog_warning": backlog_warning,
                "checked_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in queue service health check: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now().isoformat(),
            }


# ===== 全局单例 =====

_global_queue_service: Optional[QueueService] = None


def get_queue_service() -> QueueService:
    """
    获取全局队列服务实例（单例模式）

    Returns:
        QueueService 实例
    """
    global _global_queue_service

    if _global_queue_service is None:
        _global_queue_service = QueueService()
        logger.info("Global queue service created")

    return _global_queue_service


async def close_queue_service():
    """
    关闭全局队列服务（应用关闭时调用）
    """
    global _global_queue_service

    if _global_queue_service is not None:
        await _global_queue_service.close()
        _global_queue_service = None
        logger.info("Global queue service closed")
