"""
Worker 基类 - 所有异步任务 Worker 的基础

提供：
- 优雅的启动和停止
- 信号处理（SIGINT、SIGTERM）
- 并发控制
- 错误处理和重试机制
- 健康检查
- 统计信息

所有具体的 Worker 都应该继承这个基类
"""

import asyncio
import signal
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from unifiles.core.services.queue_service import QueueService, get_queue_service


class BaseWorker(ABC):
    """
    Worker 基类

    所有具体的 Worker 必须实现：
    - process_task(task: dict) -> 处理单个任务的逻辑

    使用示例：
    ```python
    class MyWorker(BaseWorker):
        def __init__(self):
            super().__init__(
                queue_name=QueueNames.FILE_UPLOAD,
                worker_name="FileUploadWorker",
                concurrency=4
            )

        async def process_task(self, task: dict):
            # 处理任务的逻辑
            file_id = task["file_id"]
            await upload_file(file_id)

    # 运行 Worker
    worker = MyWorker()
    await worker.start()
    ```
    """

    def __init__(
        self,
        queue_name: str,
        worker_name: str,
        concurrency: int = 1,
        use_priority_queue: bool = False,
        queue_service: Optional[QueueService] = None,
    ):
        """
        初始化 Worker

        Args:
            queue_name: 监听的队列名称
            worker_name: Worker 名称（用于日志和监控）
            concurrency: 并发数（同时处理的任务数）
            use_priority_queue: 是否使用优先级队列
            queue_service: 队列服务实例（可选）
        """
        self.queue_name = queue_name
        self.worker_name = worker_name
        self.concurrency = concurrency
        self.use_priority_queue = use_priority_queue
        self.queue_service = queue_service or get_queue_service()

        # Worker ID（唯一标识）
        self.worker_id = f"{worker_name}_{uuid.uuid4().hex[:8]}"

        # 运行状态
        self.running = False
        self._tasks: list[asyncio.Task] = []

        # 统计信息
        self.stats = {
            "started_at": None,
            "tasks_processed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "current_tasks": 0,
        }

    @abstractmethod
    async def process_task(self, task: dict):
        """
        处理单个任务的逻辑（由子类实现）

        Args:
            task: 任务数据字典

        Raises:
            Exception: 处理失败时抛出异常，Worker 会自动进行错误处理
        """
        pass

    # ===== 生命周期管理 =====

    async def start(self):
        """
        启动 Worker

        - 注册信号处理器
        - 初始化队列服务
        - 启动多个并发 worker 循环
        """
        logger.info(
            f"Starting {self.worker_name} (ID: {self.worker_id}) "
            f"with concurrency={self.concurrency}, queue={self.queue_name}"
        )

        # 注册信号处理
        self._setup_signal_handlers()

        # 初始化队列服务
        await self.queue_service.init()

        # 标记为运行中
        self.running = True
        self.stats["started_at"] = datetime.now().isoformat()

        # 启动多个并发 worker 循环
        for worker_index in range(self.concurrency):
            task = asyncio.create_task(
                self._worker_loop(worker_index), name=f"worker_{worker_index}"
            )
            self._tasks.append(task)

        logger.info(
            f"{self.worker_name} started with {self.concurrency} concurrent workers"
        )

        # 等待所有 worker 完成
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info(f"{self.worker_name} cancelled")

        # 清理
        await self._cleanup()

    async def stop(self):
        """
        停止 Worker（优雅退出）
        """
        logger.info(f"Stopping {self.worker_name}...")
        self.running = False

        # 取消所有正在运行的任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成（最多等待 30 秒）
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning(f"{self.worker_name} stop timeout, forcing shutdown")

        logger.info(
            f"{self.worker_name} stopped. "
            f"Processed: {self.stats['tasks_processed']}, "
            f"Succeeded: {self.stats['tasks_succeeded']}, "
            f"Failed: {self.stats['tasks_failed']}"
        )

    def _setup_signal_handlers(self):
        """设置信号处理器（优雅退出）"""

        def signal_handler(signum, frame):
            logger.info(
                f"{self.worker_name} received signal {signum}, initiating graceful shutdown..."
            )
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _cleanup(self):
        """清理资源"""
        try:
            await self.queue_service.close()
            logger.info(f"{self.worker_name} cleanup completed")
        except Exception as e:
            logger.error(f"Error during {self.worker_name} cleanup: {e}")

    # ===== Worker 主循环 =====

    async def _worker_loop(self, worker_index: int):
        """
        Worker 主循环（从队列取任务并处理）

        Args:
            worker_index: Worker 索引（用于日志）
        """
        logger.info(f"{self.worker_name}[{worker_index}] started")

        while self.running:
            try:
                # 1. 从队列取出任务（阻塞等待）
                task = await self.queue_service.dequeue_task(
                    queue_name=self.queue_name,
                    timeout=5,  # 5 秒超时，以便检查 running 状态
                    from_priority_queue=self.use_priority_queue,
                    worker_id=self.worker_id,
                )

                if not task:
                    # 队列为空或超时，继续循环
                    continue

                task_id = task.get("task_id", "unknown")
                self.stats["current_tasks"] += 1

                logger.info(
                    f"{self.worker_name}[{worker_index}] processing task {task_id}"
                )

                # 2. 处理任务
                try:
                    await self.process_task(task)

                    # 任务成功
                    await self.queue_service.complete_task(
                        task_id=task_id, worker_id=self.worker_id
                    )

                    self.stats["tasks_succeeded"] += 1
                    logger.success(
                        f"{self.worker_name}[{worker_index}] task {task_id} completed"
                    )

                except Exception as e:
                    # 任务失败
                    logger.error(
                        f"{self.worker_name}[{worker_index}] task {task_id} failed: {e}"
                    )

                    await self._handle_task_error(task, e)
                    self.stats["tasks_failed"] += 1

                finally:
                    self.stats["tasks_processed"] += 1
                    self.stats["current_tasks"] -= 1

            except asyncio.CancelledError:
                logger.info(f"{self.worker_name}[{worker_index}] cancelled")
                break
            except Exception as e:
                logger.error(f"{self.worker_name}[{worker_index}] unexpected error: {e}")
                await asyncio.sleep(1)  # 避免快速失败循环

        logger.info(f"{self.worker_name}[{worker_index}] stopped")

    async def _handle_task_error(self, task: dict, error: Exception):
        """
        处理任务错误（重试机制）

        Args:
            task: 任务数据
            error: 异常对象
        """
        task_id = task.get("task_id", "unknown")
        retry_count = task.get("retry_count", 0)
        max_retries = task.get("max_retries", 3)

        error_data = {
            "error": str(error),
            "error_type": type(error).__name__,
            "retry_count": retry_count,
        }

        if retry_count < max_retries:
            # 重新入队（带指数退避）
            delay = 2**retry_count  # 1s, 2s, 4s, 8s...
            logger.warning(
                f"Task {task_id} will be retried after {delay}s "
                f"(attempt {retry_count + 1}/{max_retries})"
            )

            await asyncio.sleep(delay)

            task["retry_count"] = retry_count + 1

            # 重新入队
            if self.use_priority_queue:
                await self.queue_service.queue_client.enqueue_priority(
                    self.queue_name, task, task.get("priority", 0)
                )
            else:
                await self.queue_service.queue_client.enqueue(self.queue_name, task)

            # 释放锁
            await self.queue_service.queue_client.release_task_lock(task_id)

        else:
            # 达到最大重试次数，标记为失败
            logger.error(
                f"Task {task_id} failed permanently after {max_retries} retries"
            )

            await self.queue_service.fail_task(
                task_id=task_id, error_data=error_data, worker_id=self.worker_id
            )

    # ===== 健康检查和监控 =====

    def get_stats(self) -> Dict[str, Any]:
        """
        获取 Worker 统计信息

        Returns:
            统计信息字典
        """
        uptime_seconds = None
        if self.stats["started_at"]:
            started = datetime.fromisoformat(self.stats["started_at"])
            uptime_seconds = (datetime.now() - started).total_seconds()

        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "queue_name": self.queue_name,
            "concurrency": self.concurrency,
            "running": self.running,
            "started_at": self.stats["started_at"],
            "uptime_seconds": uptime_seconds,
            "tasks_processed": self.stats["tasks_processed"],
            "tasks_succeeded": self.stats["tasks_succeeded"],
            "tasks_failed": self.stats["tasks_failed"],
            "current_tasks": self.stats["current_tasks"],
            "success_rate": (
                round(
                    self.stats["tasks_succeeded"]
                    / self.stats["tasks_processed"]
                    * 100,
                    2,
                )
                if self.stats["tasks_processed"] > 0
                else 0.0
            ),
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态信息
        """
        stats = self.get_stats()

        # 检查是否健康
        is_healthy = (
            self.running
            and stats["success_rate"] >= 80  # 成功率 >= 80%
            and stats["current_tasks"] < self.concurrency * 2  # 没有任务堆积
        )

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "worker": stats,
            "checked_at": datetime.now().isoformat(),
        }


# ===== 钩子方法（可选覆盖） =====

    async def on_task_start(self, task: dict):
        """
        任务开始前的钩子（可选覆盖）

        Args:
            task: 任务数据
        """
        pass

    async def on_task_complete(self, task: dict, result: Any):
        """
        任务完成后的钩子（可选覆盖）

        Args:
            task: 任务数据
            result: 任务结果
        """
        pass

    async def on_task_error(self, task: dict, error: Exception):
        """
        任务失败后的钩子（可选覆盖）

        Args:
            task: 任务数据
            error: 异常对象
        """
        pass
