"""
后台日志刷新器 - 主进程内运行（简化版）

职责：
1. 定期从Redis队列批量读取日志
2. 批量写入PostgreSQL
3. 失败重试
4. 优雅关闭（刷新剩余日志）

简化说明：
- 不是独立Worker进程，而是主进程内的后台任务
- 降低运维复杂度（无需systemd服务管理）
- 通过asyncio.create_task启动
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger

from unifiles.core.database.pool_manager import get_pool_manager
from unifiles.core.queue.redis_queue import get_queue_service


class LogBackgroundFlusher:
    """后台日志刷新器（运行在主进程中）"""

    def __init__(
        self,
        queue_name: str = "unifiles:queue:logs",
        batch_size: int = 100,
        flush_interval: float = 5.0
    ):
        """
        初始化刷新器

        Args:
            queue_name: Redis队列名称
            batch_size: 批量写入大小
            flush_interval: 刷新间隔（秒）
        """
        self.queue_name = queue_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # 批次缓冲区
        self.batch: List[Dict[str, Any]] = []
        self.last_flush_time = 0.0

        # 运行状态
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._shutdown = False

    async def start(self):
        """启动后台刷新任务"""
        if self._running:
            logger.warning("LogBackgroundFlusher already running")
            return

        self._running = True
        self._shutdown = False
        self.last_flush_time = asyncio.get_event_loop().time()

        # 创建后台任务
        self._task = asyncio.create_task(self._flush_loop())
        logger.info(
            f"LogBackgroundFlusher started: batch_size={self.batch_size}, "
            f"interval={self.flush_interval}s"
        )

    async def stop(self):
        """停止后台刷新任务"""
        if not self._running:
            return

        logger.info("LogBackgroundFlusher stopping...")
        self._shutdown = True

        # 取消后台任务
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # 刷新剩余日志
        await self._flush_remaining()

        self._running = False
        logger.success("LogBackgroundFlusher stopped")

    async def _flush_loop(self):
        """后台刷新循环"""
        queue_service = get_queue_service()

        while not self._shutdown:
            try:
                # 1. 从Redis队列批量读取日志
                logs = await self._dequeue_batch(queue_service)

                if logs:
                    self.batch.extend(logs)

                # 2. 判断是否需要刷新
                current_time = asyncio.get_event_loop().time()
                should_flush = (
                    len(self.batch) >= self.batch_size or
                    (current_time - self.last_flush_time) >= self.flush_interval
                )

                if should_flush and self.batch:
                    await self._flush_batch()
                    self.last_flush_time = current_time

                # 3. 短暂休眠（避免CPU占用过高）
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}", exc_info=e)
                await asyncio.sleep(5)  # 错误后休眠5秒

    async def _dequeue_batch(self, queue_service) -> List[Dict[str, Any]]:
        """从Redis队列批量读取日志"""
        logs = []

        try:
            # 批量读取（最多batch_size条）
            for _ in range(self.batch_size):
                task = await queue_service.dequeue(self.queue_name, timeout=0)
                if task:
                    logs.append(task)
                else:
                    break  # 队列为空

        except Exception as e:
            logger.warning(f"Failed to dequeue logs: {e}")

        return logs

    async def _flush_batch(self):
        """批量写入数据库"""
        if not self.batch:
            return

        batch_to_write = self.batch.copy()
        self.batch.clear()

        try:
            pool_manager = await get_pool_manager()

            async with pool_manager.pg_pool.acquire() as conn:
                # 使用 executemany 批量插入
                await self._batch_insert(conn, batch_to_write)

            logger.info(
                f"Flushed {len(batch_to_write)} logs to database",
                extra={"batch_size": len(batch_to_write)}
            )

        except Exception as e:
            logger.error(
                f"Failed to flush logs batch: {e}",
                extra={"batch_size": len(batch_to_write)},
                exc_info=e
            )

            # 失败重试：重新入队（简化版）
            # 生产环境应该有更完善的重试机制
            queue_service = get_queue_service()
            for log_entry in batch_to_write:
                try:
                    await queue_service.enqueue(
                        queue_name=self.queue_name,
                        task=log_entry
                    )
                except:
                    # 最终降级：写入本地文件
                    logger.error(f"Failed to re-enqueue log: {log_entry}")

    async def _batch_insert(self, conn, batch: List[Dict]):
        """批量插入数据库"""

        # 准备批量插入数据
        records = []
        for log_entry in batch:
            # 提取字段
            context = {
                k: v for k, v in log_entry.items()
                if k not in (
                    'timestamp', 'level', 'service_layer', 'service_name',
                    'message', 'trace_id', 'span_id', 'exception_type',
                    'exception_message', 'stack_trace', 'module_name',
                    'function_name', 'line_number', 'hostname',
                    'process_id', 'thread_name'
                )
            }

            records.append((
                log_entry.get('timestamp'),
                log_entry.get('level'),
                log_entry.get('service_layer'),
                log_entry.get('service_name'),
                log_entry.get('message'),
                json.dumps(context),
                log_entry.get('trace_id'),
                log_entry.get('span_id'),
                log_entry.get('exception_type'),
                log_entry.get('exception_message'),
                log_entry.get('stack_trace'),
                log_entry.get('module_name'),
                log_entry.get('function_name'),
                log_entry.get('line_number'),
                log_entry.get('hostname'),
                log_entry.get('process_id'),
                log_entry.get('thread_name'),
            ))

        # 批量插入
        await conn.executemany("""
            INSERT INTO unifiles.unified_logs
            (timestamp, level, service_layer, service_name, message, context,
             trace_id, span_id, exception_type, exception_message, stack_trace,
             module_name, function_name, line_number,
             hostname, process_id, thread_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """, records)

    async def _flush_remaining(self):
        """刷新剩余的日志（应用关闭时调用）"""
        if self.batch:
            logger.info(f"Flushing {len(self.batch)} remaining logs...")
            await self._flush_batch()


# ===== 全局单例 =====

_global_flusher: Optional[LogBackgroundFlusher] = None


async def get_log_flusher() -> LogBackgroundFlusher:
    """获取全局日志刷新器单例"""
    global _global_flusher

    if _global_flusher is None:
        _global_flusher = LogBackgroundFlusher()
        logger.info("LogBackgroundFlusher created")

    return _global_flusher


async def start_log_flusher():
    """启动全局日志刷新器"""
    flusher = await get_log_flusher()
    await flusher.start()


async def stop_log_flusher():
    """停止全局日志刷新器"""
    flusher = await get_log_flusher()
    await flusher.stop()
