from fastapi import (
    APIRouter,
    HTTPException,
    Path as FastAPIPath,
    Request,
)
from loguru import logger

from server.app.v1.schemas import FileExtractRequest, FileExtractResponse
from server.core import db, file_processor

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
    - normal: 标准文档解析
    """
    try:
        user_id = request.state.user_id
        logger.info(f"POST /files/{file_id}/extract from user: {user_id}")
        logger.info(f"Extract request: {extract_request.dict()}")

        # 1. Get file info from DB for authorization
        file_record = await db.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        if file_record["user_id"] != user_id:
            raise HTTPException(
                status_code=403, detail="Access denied: file belongs to another user"
            )

        # 2. Call the core file processor
        extracted_content = file_processor.process_file_content(
            file_id=file_id,
            file_record=file_record,
            extract_request=extract_request,
        )

        return FileExtractResponse(
            success=True,
            message="File content extracted successfully",
            extracted_content=extracted_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting file content for {file_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Content extraction failed: {str(e)}"
        )
