from datetime import datetime
from pathlib import Path
import uuid

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Path as FastAPIPath,
    Query,
    Request,
    UploadFile,
)
from loguru import logger

from server.app.v1.schemas import (
    FileInfo,
    FileListRequest,
    FileListResponse,
    FileUploadResponse,
    StandardResponse,
    SupportedFileTypes,
)
from server.core.database import file_db_manager
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
async def upload_file(
    request: Request, 
    file: UploadFile = File(...),
    is_public: bool = Query(default=False, description="是否设置为公开访问")
):
    """
    上传文件到存储

    - **file**: 要上传的文件
    - **is_public**: 是否设置为公开访问，默认为False
    - 用户ID会从请求状态中自动解析 (由AuthMiddleware提供)
    """
    try:
        user_id = request.state.user_id
        logger.info(f"POST /files request from user: {user_id}, filename: {file.filename}")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_content = await file.read()
        file_size = len(file_content)
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")

        file_id = f"file-{str(uuid.uuid4())}"
        object_path = f"{user_id}/default_file_space/{file_id}/{file.filename}"

        # 1. Upload to storage
        object_path = storage_manager.upload_file(
            object_path=object_path,
            file_content=file_content,
            file_name=file.filename,
            content_type=file.content_type,
        )
        
        # After upload, get the definitive content_type set by the storage manager
        stat = storage_manager.client.stat_object(storage_manager.bucket_name, object_path)
        content_type = stat.content_type
        
        # 2. Generate access URL based on is_public setting
        access_type = "public" if is_public else "presigned"
        public_url = storage_manager.get_file_access_url(
            object_path=object_path,
            access_type=access_type,
            expires_in_hours=24 if not is_public else None
        )

        # 3. Record in database (also update is_public status)
        await file_db_manager.add_file_record(
            file_id=file_id,
            user_id=user_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            storage_path=object_path,
            storage_config_id="example-minio",
        )
        
        # Update is_public status if needed
        if is_public:
            await file_db_manager.update_file_public_status(file_id, is_public)

        file_info = FileInfo(
            file_id=file_id,
            filename=file.filename,
            file_size=file_size,
            content_type=content_type,
            public_url=public_url,
            object_path=object_path,
            is_public=is_public,
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


@router.get("", response_model=FileListResponse)
async def list_user_files(
    request: Request,
    limit: int = Query(default=50, description="返回数量限制", ge=1, le=100),
    offset: int = Query(default=0, description="分页偏移量", ge=0),
):
    """获取当前用户的所有文件列表"""
    try:
        user_id = request.state.user_id
        logger.info(f"GET /files request from user: {user_id}, limit: {limit}, offset: {offset}")

        file_records = await file_db_manager.get_user_files(user_id, limit, offset)
        
        files = []
        for record in file_records:
            # 根据is_public字段决定URL类型
            is_public = record.get("is_public", False)
            access_type = "public" if is_public else "presigned"
            
            fresh_url = storage_manager.get_file_access_url(
                object_path=record["storage_path"],
                access_type=access_type,
                expires_in_hours=24 if not is_public else None
            )
            
            file_info = FileInfo(
                file_id=record["id"],
                filename=record["filename"],
                file_size=record["bytes"],
                content_type=record["mime_type"],
                public_url=fresh_url,
                object_path=record["storage_path"],
                is_public=is_public,
                created_at=record["created_at"].isoformat(),
            )
            files.append(file_info)

        # Check if there are more files
        has_more = len(file_records) == limit

        return FileListResponse(
            success=True,
            message="Files retrieved successfully",
            files=files,
            total_count=None,  # We could add a count query if needed
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Error getting user files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get files: {str(e)}")


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(request: Request, file_id: str = FastAPIPath(..., description="文件ID")):
    """获取文件信息"""
    try:
        logger.info(f"GET /files/{file_id} request from user: {request.state.user_id}")
        
        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        # 根据is_public字段决定URL类型
        is_public = file_record.get("is_public", False)
        access_type = "public" if is_public else "presigned"
        
        fresh_url = storage_manager.get_file_access_url(
            object_path=file_record["storage_path"],
            access_type=access_type,
            expires_in_hours=24 if not is_public else None
        )
        
        return FileInfo(
            file_id=file_record["id"],
            filename=file_record["filename"],
            file_size=file_record["bytes"],
            content_type=file_record["mime_type"],
            public_url=fresh_url,
            object_path=file_record["storage_path"],
            is_public=is_public,
            created_at=file_record["created_at"].isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info for {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")


@router.patch("/{file_id}/public-status", response_model=StandardResponse)
async def update_file_public_status(
    request: Request,
    file_id: str = FastAPIPath(..., description="文件ID"),
    is_public: bool = Query(description="是否设置为公开访问")
):
    """更新文件的公开访问状态"""
    try:
        user_id = request.state.user_id
        logger.info(f"PATCH /files/{file_id}/public-status request from user: {user_id}")
        
        # 1. 验证文件存在和权限
        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        
        if file_record["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied: file belongs to another user")
        
        # 2. 更新公开状态
        await file_db_manager.update_file_public_status(file_id, is_public)
        
        return StandardResponse(
            success=True, 
            message=f"File public status updated to: {is_public}",
            data={"file_id": file_id, "is_public": is_public}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating file public status for {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update file public status: {str(e)}")


@router.delete("/{file_id}", response_model=StandardResponse)
async def delete_file(request: Request, file_id: str = FastAPIPath(..., description="文件ID")):
    """删除文件"""
    try:
        user_id = request.state.user_id
        logger.info(f"DELETE /files/{file_id} request from user: {user_id}")

        # 1. Get file info from DB for authorization and path
        file_record = await file_db_manager.get_file_record(file_id)
        if not file_record:
            # This is idempotent, so returning success is acceptable.
            logger.warning(f"Delete request for non-existent file_id: {file_id}")
            return StandardResponse(success=True, message="File already deleted or never existed.")

        if file_record["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied: file belongs to another user")

        # 2. Delete from storage
        storage_manager.delete_file(object_path=file_record["storage_path"])

        # 3. Delete from database
        await file_db_manager.delete_file_record(file_id)

        return StandardResponse(success=True, message="File deleted successfully", data={"file_id": file_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
