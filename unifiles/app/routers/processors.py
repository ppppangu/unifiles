from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi import Path as FastAPIPath
from loguru import logger

from unifiles.app.schemas import (
    ExtractedContent,
    FileExtractRequest,
    FileExtractResponse,
)
from unifiles.core.services.document_processor import get_document_processor

# Note: The prefix is /files, but these are processing actions.
# A different prefix like /processors/{file_id} could be a future refactor.
router = APIRouter(prefix="/files", tags=["Processors"])


@router.post("/{file_id}/extract", response_model=FileExtractResponse)
async def extract_file_content(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    extract_request: FileExtractRequest = FileExtractRequest(),
) -> FileExtractResponse:
    """
    提取文件内容

    支持多种提取模式：
    - simple: 使用pdfplumber进行基础文本提取
    - mistral/mineru/selfhosted: 使用指定的OCR提供商进行多模态提取

    Args:
        request: FastAPI请求对象（包含user_id）
        file_id: 文件ID
        extract_request: 提取请求参数

    Returns:
        FileExtractResponse: 提取结果

    Raises:
        HTTPException: 404 - 文件不存在
        HTTPException: 403 - 权限不足
        HTTPException: 500 - 提取失败
    """
    try:
        user_id = request.state.user_id
        logger.info(
            f"Extracting file {file_id} for user {user_id} with mode: {extract_request.mode}"
        )

        # 调用文档处理服务
        processor = get_document_processor()
        result = await processor.process_file_by_id(
            file_id=file_id,
            user_id=user_id,
            mode=extract_request.mode,
        )

        # 构建响应
        now = datetime.now().isoformat()
        extracted_content = ExtractedContent(
            file_id=file_id,
            extraction_id=result["extraction_id"],
            content_type=result["content_type"],
            extracted_text=result.get("extracted_text"),
            markdown_content=result.get("markdown_content"),
            structured_data=result.get("structured_data"),
            extraction_metadata={
                "mode": extract_request.mode,
                "processed_at": now,
            },
            extraction_strategy=f"OCR-{extract_request.mode}",
            status="completed",
            created_at=now,
        )

        logger.info(
            f"File {file_id} extracted successfully, extraction_id: {result['extraction_id']}"
        )

        return FileExtractResponse(
            success=True,
            message="File content extracted successfully",
            extracted_content=extracted_content,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"File not found or invalid: {file_id} - {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"Permission denied for file {file_id}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error extracting file {file_id}")
        raise HTTPException(status_code=500, detail=f"Content extraction failed: {e!s}")
