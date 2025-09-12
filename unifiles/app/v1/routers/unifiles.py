from datetime import datetime
from pathlib import Path
import uuid

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Path as FastAPIPath,
    Request,
    UploadFile,
)
from loguru import logger

from server.app.v1.schemas import (
    FileInfo,
    FileUploadResponse,
    StandardResponse,
    SupportedFileTypes,
)
from server.core import db
from server.core.storage import storage_manager

# Constants from the original main.py
DOCUMENT_FILE_TYPES = [
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".ods", ".odp",
    ".txt", ".rtf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".html",
    ".htm", ".md", ".csv", ".tsv", ".xml",
]
PDF_FILE_TYPES = [".pdf"]
CODE_FILE_TYPES = [".py", ".ipynb", ".js", ".json"]
SUPPORTED_FILE_TYPES = DOCUMENT_FILE_TYPES + PDF_FILE_TYPES + CODE_FILE_TYPES

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/types", response_model=SupportedFileTypes)
async def get_supported_file_types():
    """获取支持的文件类型"""
    return SupportedFileTypes(
        document_types=DOCUMENT_FILE_TYPES,
        pdf_types=PDF_FILE_TYPES,
        code_types=CODE_FILE_TYPES,
        all_types=SUPPORTED_FILE_TYPES,
    )


@router.post("", response_model=FileUploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    上传文件到存储

    - **file**: 要上传的文件
    - 用户ID会从请求状态中自动解析 (由AuthMiddleware提供)
    """
    try:
        user_id = request.state.user_id
        logger.info(f"POST /files request from user: {user_id}, filename: {file.filename}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_type = Path(file.filename).suffix.lower()
        if file_type not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_type}. Supported types: {SUPPORTED_FILE_TYPES}",
            )

        file_content = await file.read()
        file_size = len(file_content)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")

        file_id = f"file-{str(uuid.uuid4())}"
        object_path = f"{user_id}/default_file_space/{file_id}/{file.filename}"

        # 1. Upload to storage
        public_url = storage_manager.upload_file(
            object_path=object_path,
            file_content=file_content,
            file_name=file.filename,
            content_type=file.content_type,
        )
        
        # After upload, get the definitive content_type set by the storage manager
        stat = storage_manager.client.stat_object(storage_manager.bucket_name, object_path)
        content_type = stat.content_type

        # 2. Record in database
        await db.add_file_record(
            file_id=file_id,
            user_id=user_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            object_path=object_path,
            public_url=public_url,
        )

        file_info = FileInfo(
            file_id=file_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            public_url=public_url,
            object_path=object_path,
            created_at=datetime.now().isoformat(),
        )

        return FileUploadResponse(
            success=True, message="File uploaded successfully", file=file_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(request: Request, file_id: str = FastAPIPath(..., description="文件ID")):
    """获取文件信息"""
    try:
        logger.info(f"GET /files/{file_id} request from user: {request.state.user_id}")
        
        file_record = await db.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        # Authorization is implicitly handled by middlewares or can be added here
        # if file_record["user_id"] != request.state.user_id:
        #     raise HTTPException(status_code=403, detail="Access denied")

        return FileInfo(
            file_id=file_record["id"],
            filename=file_record["filename"],
            file_size=file_record["bytes"],
            content_type=file_record["mime_type"],
            public_url=file_record["raw_file_public_url"],
            object_path=file_record["file_path"],
            created_at=file_record["created_at"].isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info for {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")


@router.delete("/{file_id}", response_model=StandardResponse)
async def delete_file(request: Request, file_id: str = FastAPIPath(..., description="文件ID")):
    """删除文件"""
    try:
        user_id = request.state.user_id
        logger.info(f"DELETE /files/{file_id} request from user: {user_id}")

        # 1. Get file info from DB for authorization and path
        file_record = await db.get_file_record(file_id)
        if not file_record:
            # This is idempotent, so returning success is acceptable.
            logger.warning(f"Delete request for non-existent file_id: {file_id}")
            return StandardResponse(success=True, message="File already deleted or never existed.")

        if file_record["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied: file belongs to another user")

        # 2. Delete from storage
        storage_manager.delete_file(object_path=file_record["file_path"])

        # 3. Delete from database
        await db.delete_file_record(file_id)

        return StandardResponse(success=True, message="File deleted successfully", data={"file_id": file_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
