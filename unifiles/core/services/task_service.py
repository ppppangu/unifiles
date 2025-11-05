"""
任务服务 - 异步任务管理业务逻辑

功能：
- 创建任务
- 查询任务状态
- 更新任务进度
- 取消任务
- 任务统计

与数据库交互，提供高级业务逻辑封装
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import HTTPException
from loguru import logger

from unifiles.config import settings
from unifiles.core.queue import QueueNames, TaskStatus, TaskTypes


class TaskService:
    """
    任务服务

    提供任务的完整生命周期管理：
    - 创建任务并入队
    - 查询任务状态
    - 更新任务进度
    - 取消任务
    - 重试失败任务
    - 任务统计

    使用示例：
    ```python
    task_service = TaskService()
    await task_service.init_pool()

    # 创建任务
    task = await task_service.create_task(
        user_id="user_123",
        task_type=TaskTypes.FILE_UPLOAD,
        task_data={"file_id": "file_456"}
    )

    # 查询任务
    status = await task_service.get_task(task["task_id"])

    # 更新进度
    await task_service.update_progress(
        task_id=task["task_id"],
        progress=50,
        message="Uploading..."
    )
    ```
    """

    def __init__(self, pg_config: Optional[Dict[str, Any]] = None):
        """
        初始化任务服务

        Args:
            pg_config: PostgreSQL 配置（可选，默认从settings读取）
        """
        if pg_config is None:
            # 使用新的settings系统构建配置字典
            self.pg_config = {
                "host": settings.database.host,
                "port": settings.database.port,
                "database": settings.database.database,
                "user": settings.database.user,
                "password": settings.database.password,
            }
        else:
            self.pg_config = pg_config
        self._connection_pool: Optional[asyncpg.Pool] = None

    async def init_pool(self, min_size: int = 5, max_size: int = 20):
        """
        初始化数据库连接池

        Args:
            min_size: 最小连接数
            max_size: 最大连接数
        """
        if not self._connection_pool:
            try:
                self._connection_pool = await asyncpg.create_pool(
                    **self.pg_config,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30,
                )
                logger.info("TaskService connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize TaskService pool: {e}")
                raise

    async def close_pool(self):
        """关闭连接池"""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
            logger.info("TaskService connection pool closed")

    # ===== 任务创建 =====

    async def create_task(
        self,
        user_id: str,
        task_type: str,
        task_data: Dict[str, Any],
        file_id: Optional[str] = None,
        priority: int = 10,
        related_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        创建任务

        Args:
            user_id: 用户 ID
            task_type: 任务类型（使用 TaskTypes 常量）
            task_data: 任务数据
            file_id: 关联的文件 ID（可选）
            priority: 优先级（0-100）
            related_task_id: 关联的父任务 ID（可选）
            metadata: 额外的元数据（可选）

        Returns:
            任务信息字典，包含 task_id

        Raises:
            HTTPException: 创建失败时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            async with self._connection_pool.acquire() as conn:
                # 调用数据库函数创建任务
                result = await conn.fetchval(
                    """
                    SELECT unifiles.create_processing_task(
                        $1, $2, $3, $4, $5, $6, $7
                    )
                    """,
                    user_id,
                    task_type,
                    json.dumps(task_data),
                    file_id,
                    priority,
                    related_task_id,
                    json.dumps(metadata or {}),
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to create task")
                    logger.error(f"Error creating task: {error_msg}")
                    raise HTTPException(status_code=500, detail=error_msg)

                task_id = result_dict.get("task_id")
                logger.info(f"Task created: {task_id} (type: {task_type})")

                return {
                    "task_id": task_id,
                    "status": TaskStatus.QUEUED,
                    "created_at": datetime.now().isoformat(),
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create task: {str(e)}"
            )

    # ===== 任务查询 =====

    async def get_task(
        self, task_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取任务详情

        Args:
            task_id: 任务 ID
            user_id: 用户 ID（用于权限验证，可选）

        Returns:
            任务详情字典

        Raises:
            HTTPException: 任务不存在或无权访问时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT unifiles.get_task_by_id($1, $2)", task_id, user_id
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error = result_dict.get("error", "task_not_found")
                    if error == "task_not_found":
                        raise HTTPException(
                            status_code=404, detail="Task not found or access denied"
                        )
                    else:
                        raise HTTPException(status_code=500, detail=result_dict.get("message"))

                return result_dict.get("task")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get task: {str(e)}"
            )

    async def get_user_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        获取用户的任务列表

        Args:
            user_id: 用户 ID
            status: 过滤状态（可选）
            task_type: 过滤任务类型（可选）
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            任务列表和总数

        Raises:
            HTTPException: 查询失败时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT unifiles.get_user_tasks($1, $2, $3, $4, $5)
                    """,
                    user_id,
                    status,
                    task_type,
                    limit,
                    offset,
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    raise HTTPException(
                        status_code=500, detail=result_dict.get("message")
                    )

                return {
                    "tasks": result_dict.get("tasks", []),
                    "total_count": result_dict.get("total_count", 0),
                    "limit": limit,
                    "offset": offset,
                    "has_more": result_dict.get("total_count", 0) > (offset + limit),
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user tasks for {user_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get user tasks: {str(e)}"
            )

    # ===== 任务更新 =====

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        progress_message: Optional[str] = None,
        result_data: Optional[Dict[str, Any]] = None,
        error_data: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态（使用 TaskStatus 常量）
            progress: 进度百分比（0-100）
            progress_message: 进度描述
            result_data: 结果数据（任务完成时）
            error_data: 错误信息（任务失败时）
            worker_id: Worker ID

        Returns:
            更新结果

        Raises:
            HTTPException: 更新失败时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT unifiles.update_task_status(
                        $1, $2, $3, $4, $5, $6, $7
                    )
                    """,
                    task_id,
                    status,
                    progress,
                    progress_message,
                    json.dumps(result_data) if result_data else None,
                    json.dumps(error_data) if error_data else None,
                    worker_id,
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    logger.warning(f"Failed to update task {task_id}: {result_dict}")

                return result_dict

        except Exception as e:
            logger.error(f"Error updating task status for {task_id}: {e}")
            # 不抛出异常，避免 Worker 中断
            return {"success": False, "error": str(e)}

    async def update_progress(
        self, task_id: str, progress: int, message: Optional[str] = None
    ) -> bool:
        """
        更新任务进度（快捷方法）

        Args:
            task_id: 任务 ID
            progress: 进度百分比（0-100）
            message: 进度描述

        Returns:
            是否更新成功
        """
        result = await self.update_status(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            progress=progress,
            progress_message=message,
        )
        return result.get("success", False)

    # ===== 任务控制 =====

    async def retry_task(self, task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        重试失败的任务

        Args:
            task_id: 任务 ID
            user_id: 用户 ID（用于权限验证）

        Returns:
            重试结果

        Raises:
            HTTPException: 重试失败时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            # 验证权限
            if user_id:
                task = await self.get_task(task_id, user_id)
                if not task:
                    raise HTTPException(
                        status_code=404, detail="Task not found or access denied"
                    )

            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT unifiles.retry_failed_task($1)", task_id
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error = result_dict.get("error")
                    if error == "max_retries_exceeded":
                        raise HTTPException(
                            status_code=400, detail="Maximum retry count exceeded"
                        )
                    elif error == "invalid_status":
                        raise HTTPException(
                            status_code=400,
                            detail="Only failed or cancelled tasks can be retried",
                        )
                    else:
                        raise HTTPException(
                            status_code=500, detail=result_dict.get("message")
                        )

                logger.info(f"Task {task_id} queued for retry")
                return result_dict

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrying task {task_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to retry task: {str(e)}"
            )

    # ===== 任务统计 =====

    async def get_statistics(
        self,
        user_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        获取任务统计信息

        Args:
            user_id: 用户 ID（可选，不指定则查询全部）
            since: 起始时间（可选，默认最近 7 天）

        Returns:
            统计信息字典

        Raises:
            HTTPException: 查询失败时抛出
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            if since is None:
                since = datetime.now() - timedelta(days=7)

            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT unifiles.get_task_statistics($1, $2)", user_id, since
                )

                return json.loads(result)

        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get task statistics: {str(e)}"
            )

    # ===== 清理 =====

    async def cleanup_old_tasks(self, days_to_keep: int = 30) -> int:
        """
        清理旧任务

        Args:
            days_to_keep: 保留天数（默认 30 天）

        Returns:
            删除的任务数量
        """
        try:
            if not self._connection_pool:
                await self.init_pool()

            async with self._connection_pool.acquire() as conn:
                deleted_count = await conn.fetchval(
                    "SELECT unifiles.cleanup_old_tasks($1)", days_to_keep
                )

                if deleted_count and deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old tasks")

                return deleted_count or 0

        except Exception as e:
            logger.error(f"Error cleaning up old tasks: {e}")
            return 0
