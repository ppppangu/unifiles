"""
异步任务管理路由器
提供任务状态查询、结果获取、任务取消等功能
"""
import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi import Path as FastAPIPath

from unifiles.app.schemas import (
    ExtractedContent,
    TaskInfo,
    TaskListResponse,
    TaskResultResponse,
    TaskStatusResponse,
)
from unifiles.core.database import async_task_manager, extraction_db_manager
from unifiles.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    request: Request,
    task_id: str = FastAPIPath(..., description="任务ID"),
) -> TaskStatusResponse:
    """
    查询任务状态和进度

    Args:
        request: FastAPI请求对象（包含user_id）
        task_id: 任务ID

    Returns:
        TaskStatusResponse: 任务状态响应

    Raises:
        HTTPException: 404 - 任务不存在
        HTTPException: 403 - 权限不足
    """
    user_id = request.state.user_id

    

    try:
        # 获取任务详情
        task = await async_task_manager.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # 验证权限
        if task["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Access denied: task belongs to another user"
            )

        # 构建响应
        return TaskStatusResponse(
            task_id=task["id"],
            task_type=task["task_type"],
            status=task["status"],
            progress_percent=task["progress_percent"],
            progress_message=task.get("progress_message"),
            entity_type=task.get("entity_type"),
            entity_id=task.get("entity_id"),
            created_at=task["created_at"].isoformat(),
            started_at=task["started_at"].isoformat() if task.get("started_at") else None,
            completed_at=(
                task["completed_at"].isoformat() if task.get("completed_at") else None
            ),
            error_message=task.get("error_message"),
            retry_count=task.get("retry_count", 0),
            max_retries=task.get("max_retries", 3),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get task status for {task_id}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {e!s}"
        )


@router.get("/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(
    request: Request,
    task_id: str = FastAPIPath(..., description="任务ID"),
) -> TaskResultResponse:
    """
    获取任务结果（仅适用于已完成的任务）

    Args:
        request: FastAPI请求对象（包含user_id）
        task_id: 任务ID

    Returns:
        TaskResultResponse: 任务结果响应

    Raises:
        HTTPException: 404 - 任务不存在
        HTTPException: 403 - 权限不足
        HTTPException: 400 - 任务未完成
    """
    user_id = request.state.user_id

    try:
        # 获取任务详情
        task = await async_task_manager.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        # 验证权限
        if task["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Access denied: task belongs to another user"
            )

        # 检查任务状态
        if task["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed yet. Current status: {task['status']}",
            )

        # 获取结果数据（JSONB 字段需要反序列化）
        result_data = task.get("result_data", "{}")
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data or "{}")
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Failed to parse result_data for task {task_id}")
                result_data = {}

        # 如果是提取任务，获取提取内容
        extracted_content = None
        if task["task_type"] == "extraction" and result_data.get("extraction_id"):
            extraction_id = result_data["extraction_id"]

            # 从数据库获取提取文档
            extracted_doc = await extraction_db_manager.get_extracted_document(
                extraction_id=extraction_id,
                user_id=user_id,
            )

            if extracted_doc:
                # 反序列化 JSONB 字段（数据库字段名是 performance_metrics）
                performance_metrics = extracted_doc.get("performance_metrics", "{}")
                if isinstance(performance_metrics, str):
                    try:
                        performance_metrics = json.loads(performance_metrics or "{}")
                    except (json.JSONDecodeError, ValueError):
                        performance_metrics = {}

                extracted_content = ExtractedContent(
                    file_id=task["entity_id"],
                    extraction_id=extraction_id,
                    content_type="text/markdown",
                    extracted_text=extracted_doc.get("full_markdown", ""),
                    markdown_content=extracted_doc.get("full_markdown", ""),
                    structured_data={
                        "total_chars": extracted_doc.get("total_chars", 0),
                        "total_pages": extracted_doc.get("total_pages", 0),
                        "total_assets": extracted_doc.get("total_assets", 0),
                    },
                    extraction_metadata=performance_metrics,
                    extraction_strategy=extracted_doc.get("strategy_name", ""),
                    status=extracted_doc.get("extraction_status", "completed"),
                    created_at=extracted_doc["created_at"].isoformat(),
                )

        return TaskResultResponse(
            task_id=task_id,
            status=task["status"],
            result_data=result_data,
            extracted_content=extracted_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get task result for {task_id}")
        raise HTTPException(status_code=500, detail=f"Failed to get task result: {e!s}")


@router.delete("/{task_id}")
async def cancel_task(
    request: Request,
    task_id: str = FastAPIPath(..., description="任务ID"),
):
    """
    取消任务（仅适用于 pending/queued/processing 状态的任务）

    Args:
        request: FastAPI请求对象（包含user_id）
        task_id: 任务ID

    Returns:
        dict: 取消结果

    Raises:
        HTTPException: 404 - 任务不存在
        HTTPException: 403 - 权限不足
        HTTPException: 400 - 任务不能被取消
    """
    user_id = request.state.user_id

    try:
        # 尝试取消任务
        success = await async_task_manager.cancel_task(task_id, user_id)

        if not success:
            # 获取任务详情以提供更详细的错误信息
            task = await async_task_manager.get_task_by_id(task_id)

            if not task:
                raise HTTPException(
                    status_code=404, detail=f"Task not found: {task_id}"
                )

            if task["user_id"] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: task belongs to another user",
                )

            raise HTTPException(
                status_code=400,
                detail=f"Task cannot be cancelled. Current status: {task['status']}",
            )

        logger.info(f"Task {task_id} cancelled by user {user_id}")

        return {"success": True, "message": f"Task {task_id} cancelled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to cancel task {task_id}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {e!s}")


@router.get("", response_model=TaskListResponse)
async def list_user_tasks(
    request: Request,
    status: Optional[str] = Query(
        None, description="任务状态过滤（可选，如 pending,processing）"
    ),
    task_type: Optional[str] = Query(None, description="任务类型过滤（可选）"),
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
) -> TaskListResponse:
    """
    列出用户的任务列表

    Args:
        request: FastAPI请求对象（包含user_id）
        status: 状态过滤（逗号分隔，如 "pending,processing"）
        task_type: 任务类型过滤
        limit: 返回数量限制
        offset: 分页偏移量

    Returns:
        TaskListResponse: 任务列表响应
    """
    user_id = request.state.user_id

    try:
        # 解析状态过滤
        status_filter = None
        if status:
            status_filter = [s.strip() for s in status.split(",")]

        # 获取任务列表
        tasks = await async_task_manager.get_user_tasks(
            user_id=user_id,
            status_filter=status_filter,
            task_type_filter=task_type,
            limit=limit,
            offset=offset,
        )

        # 构建响应
        task_list = []
        for task in tasks:
            task_list.append(
                TaskInfo(
                    task_id=task["id"],
                    task_type=task["task_type"],
                    status=task["status"],
                    progress_percent=task["progress_percent"],
                    progress_message=task.get("progress_message"),
                    entity_type=task.get("entity_type"),
                    entity_id=task.get("entity_id"),
                    created_at=task["created_at"].isoformat(),
                    started_at=(
                        task["started_at"].isoformat() if task.get("started_at") else None
                    ),
                    completed_at=(
                        task["completed_at"].isoformat()
                        if task.get("completed_at")
                        else None
                    ),
                    error_message=task.get("error_message"),
                    priority=task.get("priority", 5),
                )
            )

        return TaskListResponse(
            success=True,
            message=f"Retrieved {len(task_list)} tasks",
            tasks=task_list,
            total_count=len(task_list),
            has_more=len(task_list) == limit,  # 简单判断是否有更多数据
        )

    except Exception as e:
        logger.exception("Failed to list user tasks")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {e!s}")
