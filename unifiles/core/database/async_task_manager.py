"""
异步任务数据库管理器
管理 async_tasks 表的 CRUD 操作
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from unifiles.core.logging import get_logger

from .base_manager import BaseDBManager

logger = get_logger()


class AsyncTaskManager(BaseDBManager):
    """异步任务数据库管理器"""

    def __init__(self):
        super().__init__()

    async def create_task(
        self,
        task_type: str,
        user_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        celery_task_id: Optional[str] = None,
    ) -> str:
        """
        创建异步任务记录

        Args:
            task_type: 任务类型（extraction, chunking, embedding, indexing）
            user_id: 用户ID
            entity_type: 实体类型（file, extracted_document, document等）
            entity_id: 实体ID
            input_params: 输入参数（JSON）
            priority: 优先级（1-10，数字越小优先级越高）
            celery_task_id: Celery 任务ID

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())

        query = f"""
            INSERT INTO {self._schema_name}.async_tasks (
                id, task_type, task_category, entity_type, entity_id,
                status, progress_percent, input_params, user_id,
                priority, celery_task_id, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """

        await self.execute_query(
            query,
            task_id,
            task_type,
            "processing",  # task_category
            entity_type,
            entity_id,
            "pending",  # status
            0,  # progress_percent
            json.dumps(input_params or {}),  # 转换为JSON字符串
            user_id,
            priority,
            celery_task_id,
            datetime.now(),
            user_id=user_id,
            operation="create_task",
        )

        logger.info(f"Created async task: {task_id} (type={task_type}, user={user_id})")
        return task_id

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress_message: Optional[str] = None,
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态（pending, queued, processing, completed, failed, cancelled）
            progress_message: 进度消息

        Returns:
            是否更新成功
        """
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET status = $1, progress_message = $2
            WHERE id = $3
        """

        result = await self.execute_query(query, status, progress_message, task_id)
        success = result and "UPDATE" in result

        if success:
            logger.info(f"Task {task_id} status updated to: {status}")
        return success

    async def update_task_progress(
        self,
        task_id: str,
        progress_percent: int,
        progress_message: Optional[str] = None,
    ) -> bool:
        """
        更新任务进度

        Args:
            task_id: 任务ID
            progress_percent: 进度百分比（0-100）
            progress_message: 进度消息

        Returns:
            是否更新成功
        """
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET progress_percent = $1, progress_message = $2
            WHERE id = $3
        """

        result = await self.execute_query(query, progress_percent, progress_message, task_id)
        return result and "UPDATE" in result

    async def mark_task_completed(
        self,
        task_id: str,
        result_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        标记任务为已完成

        Args:
            task_id: 任务ID
            result_data: 任务结果数据（JSON）

        Returns:
            是否更新成功
        """
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET status = 'completed',
                progress_percent = 100,
                progress_message = 'Task completed successfully',
                result_data = $1,
                completed_at = $2
            WHERE id = $3
        """

        result = await self.execute_query(
            query,
            json.dumps(result_data or {}),  # 转换为JSON字符串
            datetime.now(),
            task_id,
        )
        success = result and "UPDATE" in result

        if success:
            logger.info(f"Task {task_id} marked as completed")
        return success

    async def mark_task_failed(
        self,
        task_id: str,
        error_message: str,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
    ) -> bool:
        """
        标记任务为失败

        Args:
            task_id: 任务ID
            error_message: 错误消息
            error_code: 错误代码
            error_details: 错误详情（JSON）
            stack_trace: 堆栈跟踪

        Returns:
            是否更新成功
        """
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET status = 'failed',
                error_message = $1,
                error_code = $2,
                error_details = $3,
                stack_trace = $4,
                completed_at = $5
            WHERE id = $6
        """

        result = await self.execute_query(
            query,
            error_message,
            error_code,
            json.dumps(error_details or {}),  # 转换为JSON字符串
            stack_trace,
            datetime.now(),
            task_id,
        )
        success = result and "UPDATE" in result

        if success:
            logger.error(f"Task {task_id} marked as failed: {error_message}")
        return success

    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取任务详情

        Args:
            task_id: 任务ID

        Returns:
            任务详情字典，如果不存在则返回None
        """
        query = f"""
            SELECT
                id, task_type, task_category, entity_type, entity_id,
                status, progress_percent, progress_message,
                input_params, result_data,
                error_message, error_code, error_details, stack_trace,
                user_id, created_at, queued_at, started_at, completed_at,
                retry_count, max_retries, priority, celery_task_id
            FROM {self._schema_name}.async_tasks
            WHERE id = $1
        """

        return await self.fetch_one(query, task_id)

    async def get_user_tasks(
        self,
        user_id: str,
        status_filter: Optional[List[str]] = None,
        task_type_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        获取用户的任务列表

        Args:
            user_id: 用户ID
            status_filter: 状态过滤列表（如 ['pending', 'processing']）
            task_type_filter: 任务类型过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        conditions = ["user_id = $1"]
        params = [user_id]
        param_count = 1

        if status_filter:
            param_count += 1
            conditions.append(f"status = ANY(${param_count})")
            params.append(status_filter)

        if task_type_filter:
            param_count += 1
            conditions.append(f"task_type = ${param_count}")
            params.append(task_type_filter)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                id, task_type, entity_type, entity_id,
                status, progress_percent, progress_message,
                created_at, started_at, completed_at,
                error_message, priority
            FROM {self._schema_name}.async_tasks
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """

        params.extend([limit, offset])
        return await self.fetch_all(query, *params)

    async def cancel_task(self, task_id: str, user_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID
            user_id: 用户ID（用于权限验证）

        Returns:
            是否取消成功
        """
        # 只能取消 pending, queued, processing 状态的任务
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET status = 'cancelled',
                completed_at = $1
            WHERE id = $2
              AND user_id = $3
              AND status IN ('pending', 'queued', 'processing')
        """

        result = await self.execute_query(query, datetime.now(), task_id, user_id)
        success = result and "UPDATE 1" in result

        if success:
            logger.info(f"Task {task_id} cancelled by user {user_id}")
        return success

    async def increment_retry_count(self, task_id: str) -> bool:
        """
        增加任务重试次数

        Args:
            task_id: 任务ID

        Returns:
            是否更新成功
        """
        query = f"""
            UPDATE {self._schema_name}.async_tasks
            SET retry_count = retry_count + 1,
                last_retry_at = $1
            WHERE id = $2
        """

        result = await self.execute_query(query, datetime.now(), task_id)
        return result and "UPDATE" in result

    async def cleanup_expired_tasks(self, user_id: Optional[str] = None) -> int:
        """
        清理过期的已完成任务

        Args:
            user_id: 用户ID（可选，如果指定则只清理该用户的任务）

        Returns:
            清理的任务数量
        """
        if user_id:
            query = f"""
                DELETE FROM {self._schema_name}.async_tasks
                WHERE expires_at < $1
                  AND status IN ('completed', 'failed', 'cancelled')
                  AND user_id = $2
            """
            result = await self.execute_query(query, datetime.now(), user_id)
        else:
            query = f"""
                DELETE FROM {self._schema_name}.async_tasks
                WHERE expires_at < $1
                  AND status IN ('completed', 'failed', 'cancelled')
            """
            result = await self.execute_query(query, datetime.now())

        # 从结果中提取删除的行数
        if result and "DELETE" in result:
            count = int(result.split()[-1])
            logger.info(f"Cleaned up {count} expired tasks")
            return count
        return 0


# 全局单例实例
_async_task_manager: Optional[AsyncTaskManager] = None


def get_async_task_manager() -> AsyncTaskManager:
    """获取异步任务管理器单例实例"""
    global _async_task_manager
    if _async_task_manager is None:
        _async_task_manager = AsyncTaskManager()
    return _async_task_manager


# 默认实例（用于导入）
async_task_manager = get_async_task_manager()
