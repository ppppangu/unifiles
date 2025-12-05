from fastapi import APIRouter, HTTPException, Request
from fastapi import Path as FastAPIPath

from unifiles.core.logging import get_logger

logger = get_logger()

from unifiles.app.schemas import (
    FileExtractRequest,
    TaskSubmitResponse,
)
from unifiles.core.celery.tasks import process_file_extraction_task
from unifiles.core.database import async_task_manager, unified_file_db_manager

# Note: The prefix is /files, but these are processing actions.
# A different prefix like /processors/{file_id} could be a future refactor.
router = APIRouter(prefix="/files", tags=["Processors"])


@router.post("/{file_id}/extract", response_model=TaskSubmitResponse)
async def extract_file_content(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    extract_request: FileExtractRequest = FileExtractRequest(),
) -> TaskSubmitResponse:
    """
    提取文件内容（异步）

    该端点会立即返回任务ID，实际提取工作在后台 Celery Worker 中执行。
    使用 GET /tasks/{task_id} 查询任务状态和进度。

    支持多种提取模式：
    - simple: 使用pdfplumber进行基础文本提取
    - mistral/mineru/selfhosted/openai: 使用指定的OCR提供商进行多模态提取

    Args:
        request: FastAPI请求对象（包含user_id）
        file_id: 文件ID
        extract_request: 提取请求参数

    Returns:
        TaskSubmitResponse: 包含任务ID的响应

    Raises:
        HTTPException: 404 - 文件不存在
        HTTPException: 403 - 权限不足
        HTTPException: 500 - 任务创建失败
    """
    try:
        user_id = request.state.user_id
        logger.info(
            f"Submitting extraction task for file {file_id}, user {user_id}, mode: {extract_request.mode}"
        )

        # 验证文件存在且用户有权限访问
        file_record = await unified_file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        if file_record["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: file belongs to another user",
            )

        # 数据库中创建异步任务记录
        task_id = await async_task_manager.create_task(
            task_type="extraction",
            user_id=user_id,
            entity_type="file",
            entity_id=file_id,
            input_params={
                "file_id": file_id,
                "mode": extract_request.mode,
                "parse_image_content": extract_request.parse_image_content,
                "filename": file_record.get("filename", "unknown"),
            },
            priority=5,
        )

        logger.info(f"Created async task: {task_id} for file {file_id}")

        # 提交 Celery 任务
        celery_task = process_file_extraction_task.apply_async(
            args=[
                file_id,
                user_id,
                task_id,
                extract_request.mode,
                extract_request.parse_image_content,
            ],
            task_id=task_id,  # 使用数据库任务ID作为Celery任务ID
        )

        logger.info(f"Submitted Celery task: {celery_task.id} for file {file_id}")

        # 更新任务状态为 queued
        await async_task_manager.update_task_status(
            task_id=task_id,
            status="queued",
            progress_message="Task queued in RabbitMQ",
        )

        return TaskSubmitResponse(
            task_id=task_id,
            status="queued",
            message="Extraction task submitted successfully. Use GET /tasks/{task_id} to check status.",
            file_id=file_id,
            entity_id=file_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to submit extraction task for file {file_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit extraction task: {e!s}",
        )
