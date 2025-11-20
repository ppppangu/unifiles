"""
Celery 任务定义
定义所有异步任务，包括文件提取、分块、嵌入等
"""
import asyncio
import traceback
from typing import Any, Dict, Optional

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from unifiles.core.celery.app import celery_app
from unifiles.core.database import async_task_manager
from unifiles.core.logging import get_logger
from unifiles.core.services.document_processor import get_document_processor

logger = get_logger()


# 全局事件循环（每个 Worker 进程一个）
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    获取或创建事件循环

    在 Celery Worker 进程中复用同一个事件循环，避免重复创建/关闭导致的问题
    """
    global _event_loop

    if _event_loop is None or _event_loop.is_closed():
        logger.info("Creating new event loop for Celery worker process")
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)

    return _event_loop


def run_async(coro):
    """
    在 Celery 任务中安全地运行异步代码

    使用共享的事件循环，避免 asyncio.run() 在进程复用时的问题
    """
    loop = get_or_create_event_loop()
    return loop.run_until_complete(coro)


class CallbackTask(Task):
    """带回调功能的任务基类"""

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功回调"""
        logger.info(f"Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试回调"""
        logger.warning(f"Task {task_id} retry: {exc}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="unifiles.core.celery.tasks.process_file_extraction_task",
    max_retries=3,
    default_retry_delay=10,  # 重试延迟10秒
    autoretry_for=(Exception,),  # 自动重试所有异常
    retry_backoff=True,  # 指数退避
    retry_backoff_max=600,  # 最大退避时间10分钟
    retry_jitter=True,  # 添加随机抖动避免重试风暴
)
def process_file_extraction_task(
    self,
    file_id: str,
    user_id: str,
    task_db_id: str,
    mode: str = "simple",
    parse_image_content: bool = False,
) -> Dict[str, Any]:
    """
    OCR 文件提取异步任务

    Args:
        self: Celery task 实例
        file_id: 文件ID
        user_id: 用户ID
        task_db_id: 数据库中的任务ID
        mode: 提取模式(simple, mistral, selfhosted等)
        parse_image_content: 是否解析图像内容到full_markdown

    Returns:
        提取结果字典
    """
    logger.info(
        f"Starting extraction task for file {file_id}, user {user_id}, mode {mode}"
    )

    async def _update_task_status(status: str, progress: int = 0, message: str = ""):
        """更新任务状态的辅助函数"""
        try:
            await async_task_manager.update_task_status(
                task_id=task_db_id, status=status, progress_message=message
            )
            if progress > 0:
                await async_task_manager.update_task_progress(
                    task_id=task_db_id,
                    progress_percent=progress,
                    progress_message=message,
                )
        except Exception as e:
            logger.warning(f"Failed to update task status: {e}")

    async def _run_extraction():
        """执行提取的异步函数"""
        try:
            # 更新状态为 processing
            await _update_task_status("processing", 10, "Starting file processing")

            # 获取文档处理服务
            processor = get_document_processor()

            # 更新进度
            await _update_task_status("processing", 20, "Processing file")

            # 执行提取
            result = await processor.process_file_by_id(
                file_id=file_id, user_id=user_id, mode=mode, parse_image_content=parse_image_content
            )

            # 更新进度
            await _update_task_status("processing", 90, "Finalizing results")

            # 标记任务完成
            await async_task_manager.mark_task_completed(
                task_id=task_db_id,
                result_data={
                    "extraction_id": result["extraction_id"],
                    "content_type": result["content_type"],
                    "markdown_length": len(result.get("markdown_content", "")),
                    "structured_data": result.get("structured_data", {}),
                },
            )

            logger.info(
                f"Extraction completed for file {file_id}: {result['extraction_id']}"
            )

            return {
                "success": True,
                "extraction_id": result["extraction_id"],
                "file_id": file_id,
                "message": "File extracted successfully",
            }

        except SoftTimeLimitExceeded:
            # 软超时异常
            error_msg = f"Task exceeded time limit for file {file_id}"
            logger.error(error_msg)
            await async_task_manager.mark_task_failed(
                task_id=task_db_id,
                error_message=error_msg,
                error_code="TIMEOUT",
            )
            raise

        except Exception as e:
            # 其他异常
            error_msg = f"Extraction failed for file {file_id}: {e!s}"
            stack_trace = traceback.format_exc()
            logger.exception(error_msg)

            # 检查是否还能重试
            if self.request.retries < self.max_retries:
                # 只在还能重试时增加重试计数
                await async_task_manager.increment_retry_count(task_db_id)
                await _update_task_status(
                    "processing",
                    0,
                    f"Retrying... ({self.request.retries + 1}/{self.max_retries})",
                )
                # Celery 会自动重试
                raise
            else:
                # 已达到最大重试次数，标记为失败
                await async_task_manager.mark_task_failed(
                    task_id=task_db_id,
                    error_message=error_msg,
                    error_code="EXTRACTION_FAILED",
                    error_details={"file_id": file_id, "mode": mode},
                    stack_trace=stack_trace,
                )
                raise

    # 运行异步函数（使用共享的事件循环）
    try:
        result = run_async(_run_extraction())
        return result
    except Exception as e:
        logger.exception(f"Task execution failed: {e}")
        raise


@celery_app.task(name="unifiles.core.celery.tasks.cleanup_expired_tasks_task")
def cleanup_expired_tasks_task() -> Dict[str, Any]:
    """
    清理过期任务的定时任务

    Returns:
        清理结果字典
    """
    logger.info("Starting cleanup of expired tasks")

    async def _cleanup():
        count = await async_task_manager.cleanup_expired_tasks()
        return {"cleaned_count": count}

    try:
        result = run_async(_cleanup())
        logger.info(f"Cleaned up {result['cleaned_count']} expired tasks")
        return result
    except Exception as e:
        logger.exception(f"Failed to cleanup expired tasks: {e}")
        raise


# 为了方便测试，添加一个简单的测试任务
@celery_app.task(name="unifiles.core.celery.tasks.test_task")
def test_task(message: str = "Hello from Celery!") -> Dict[str, Any]:
    """
    测试任务

    Args:
        message: 测试消息

    Returns:
        测试结果字典
    """
    logger.info(f"Test task executed: {message}")
    return {"success": True, "message": message, "task_id": test_task.request.id}
