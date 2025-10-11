from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)
from fastapi import (
    Path as FastAPIPath,
)
from loguru import logger

from unifiles.app.schemas import (
    FileExtractRequest,
    FileExtractResponse,
    ExtractedContent
)
from unifiles.core.database import secure_file_db_manager
from unifiles.core.services.document_processor import get_document_processor

# Note: The prefix is /files, but these are processing actions.
# A different prefix like /processors/{file_id} could be a future refactor.
router = APIRouter(prefix="/files", tags=["Processors"])


@router.post("/{file_id}/extract", response_model=FileExtractResponse)
async def extract_file_content(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    extract_request: FileExtractRequest = FileExtractRequest(),
):
    """
    提取文件内容

    支持多种提取模式：
    - simple: 基础文本提取
    - ocr提供商名称: 使用指定的OCR提供商
    """
    try:
        user_id = request.state.user_id
        logger.info(f"POST /files/{file_id}/extract from user: {user_id}")
        logger.info(f"Extract request: {extract_request.dict()}")

        # 调用文档处理服务
        processor = get_document_processor()
        extracted_content_data = await processor.process_file_by_id(
            file_id=file_id,
            user_id=user_id,
            mode=extract_request.mode,
        )

        # 构建响应
        import uuid
        from datetime import datetime

        extracted_content = ExtractedContent(
            file_id=file_id,
            extraction_id=f"ext_{str(uuid.uuid4())[:8]}",
            content_type=extracted_content_data["content_type"],
            extracted_text=extracted_content_data["extracted_text"],
            markdown_content=extracted_content_data["markdown_content"],
            structured_data=extracted_content_data["structured_data"],
            extraction_metadata={"mode": extract_request.mode, "processed_at": datetime.now().isoformat()},
            status="completed",
            created_at=datetime.now().isoformat()
        )

        return FileExtractResponse(
            success=True,
            message="File content extracted successfully",
            extracted_content=extracted_content,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Error extracting file content for {file_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"Error extracting file content for {file_id}: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting file content for {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Content extraction failed: {e!s}")
