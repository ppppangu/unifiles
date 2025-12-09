from fastapi import APIRouter, HTTPException, Request
from fastapi import Path as FastAPIPath

from unifiles.core.logging import get_logger

logger = get_logger()

from unifiles.app.schemas import (
    ExtractedContent,
    FileExtractRequest,
    FileExtractResponse,
    TaskSubmitResponse,
)
from unifiles.core.celery.tasks import process_file_extraction_task
from unifiles.core.database import async_task_manager, unified_file_db_manager

# Content extraction endpoints
# These endpoints handle document content extraction (Layer 2 of the three-layer architecture)
router = APIRouter(prefix="/extractions", tags=["Extractions"])


@router.post("/{file_id}", response_model=TaskSubmitResponse)
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


@router.get("/{file_id}", response_model=FileExtractResponse)
async def get_extracted_content(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
) -> FileExtractResponse:
    """
    获取文件提取后的全部内容

    该端点返回文件经过提取处理后的完整内容，包括 Markdown 格式的全文。
    如果文件尚未提取，将返回 404 错误。

    Args:
        request: FastAPI请求对象（包含user_id）
        file_id: 文件ID

    Returns:
        FileExtractResponse: 包含提取内容的响应

    Raises:
        HTTPException: 404 - 文件不存在或未提取
        HTTPException: 403 - 权限不足
        HTTPException: 500 - 服务器错误
    """
    from unifiles.core.database import extraction_db_manager

    try:
        user_id = request.state.user_id
        logger.info(f"Getting extracted content for file {file_id}, user {user_id}")

        # 验证文件存在且用户有权限访问
        file_record = await unified_file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        if file_record["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: file belongs to another user",
            )

        # 获取该文件的提取记录（取最新的一条）
        extracted_docs = await extraction_db_manager.get_extracted_documents_by_file(
            file_id=file_id, user_id=user_id
        )

        if not extracted_docs:
            raise HTTPException(
                status_code=404,
                detail=f"No extracted content found for file: {file_id}. Please extract the file first using POST /{file_id}/extract",
            )

        # 获取最新的提取记录（按创建时间排序，取第一条）
        latest_extraction = extracted_docs[0]
        extraction_id = latest_extraction["id"]

        # 获取完整的提取内容（包含 full_markdown）
        full_extraction = await extraction_db_manager.get_extracted_document(
            extraction_id=extraction_id, user_id=user_id
        )

        if not full_extraction:
            raise HTTPException(
                status_code=404,
                detail=f"Extracted document not found: {extraction_id}",
            )

        # 构建响应
        extracted_content = ExtractedContent(
            file_id=file_id,
            extraction_id=extraction_id,
            content_type="markdown",
            extracted_text=full_extraction.get("full_markdown"),
            markdown_content=full_extraction.get("full_markdown"),
            structured_data=None,
            extraction_metadata={
                "total_pages": full_extraction.get("total_pages", 0),
                "total_chars": full_extraction.get("total_chars", 0),
                "total_assets": full_extraction.get("total_assets", 0),
                "strategy_name": full_extraction.get("strategy_name"),
                "strategy_type": full_extraction.get("strategy_type"),
                "processing_config": full_extraction.get("processing_config"),
                "performance_metrics": full_extraction.get("performance_metrics"),
            },
            extraction_strategy=full_extraction.get("strategy_name"),
            status=full_extraction.get("extraction_status", "completed"),
            created_at=full_extraction["created_at"].isoformat(),
        )

        logger.info(f"Successfully retrieved extracted content for file {file_id}")

        return FileExtractResponse(
            success=True,
            message="Extracted content retrieved successfully",
            extracted_content=extracted_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get extracted content for file {file_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get extracted content: {e!s}",
        )
