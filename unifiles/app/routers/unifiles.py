from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi import (
    Path as FastAPIPath,
)

from unifiles.app.schemas import (
    FileInfo,
    FileListResponse,
    FileUploadResponse,
    StandardResponse,
    SupportedFileTypes,
)
from unifiles.core.database import unified_file_db_manager
from unifiles.core.logging import get_logger
from unifiles.core.services import AuthService, FileService
from unifiles.core.storage import get_initialized_storage

logger = get_logger()


# 创建服务实例
async def get_file_service() -> FileService:
    """获取文件服务实例"""
    storage = await get_initialized_storage()
    return FileService(storage, unified_file_db_manager)


def get_auth_service() -> AuthService:
    """获取认证服务实例"""
    from unifiles.core.config.env_config import read_pg_config

    return AuthService(read_pg_config())


# 依赖注入
async def get_user_context(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """提取用户上下文"""
    return await auth_service.extract_user_from_request(request)


# 常量定义（从原文件迁移）
DOCUMENT_FILE_TYPES = [
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".txt",
    ".rtf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".tif",
    ".bmp",
    ".html",
    ".htm",
    ".md",
    ".csv",
    ".tsv",
    ".xml",
]
PDF_FILE_TYPES = [".pdf"]
CODE_FILE_TYPES = [".py", ".ipynb", ".js", ".json"]
SUPPORTED_FILE_TYPES = DOCUMENT_FILE_TYPES + PDF_FILE_TYPES + CODE_FILE_TYPES

router = APIRouter(prefix="/files", tags=["Files (Secure)"])


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
    file: UploadFile = File(...),
    is_public: bool = Query(default=False, description="是否设置为公开访问"),
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """
    安全上传文件到存储

    - **file**: 要上传的文件
    - **is_public**: 是否设置为公开访问，默认为False
    - 用户ID会从请求状态中自动解析 (由AuthMiddleware提供)
    """
    try:
        user_id = user_context["user_id"]
        logger.info(
            f"POST /files request from user: {user_id}, filename: {file.filename}"
        )

        # 使用服务层处理文件上传
        result = await file_service.upload_file(
            user_id=user_id,
            file=file,
            is_public=is_public,
            metadata={
                "client_ip": user_context.get("client_ip"),
                "user_agent": user_context.get("user_agent"),
                "upload_source": "api_v1",
            },
        )

        logger.info(f"File uploaded successfully: {result.file.file_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in upload file endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e!s}")


@router.get("", response_model=FileListResponse)
async def list_user_files(
    limit: int = Query(default=50, description="返回数量限制", ge=1, le=100),
    offset: int = Query(default=0, description="分页偏移量", ge=0),
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """获取当前用户的所有文件列表"""
    try:
        user_id = user_context["user_id"]
        logger.info(
            f"GET /files request from user: {user_id}, limit: {limit}, offset: {offset}"
        )

        # 使用服务层获取文件列表
        result = await file_service.get_user_files(
            user_id=user_id, limit=limit, offset=offset
        )

        logger.info(f"Retrieved {len(result.files)} files for user: {user_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list files endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get files: {e!s}")


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(
    file_id: str = FastAPIPath(..., description="文件ID"),
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """获取文件信息"""
    try:
        user_id = user_context["user_id"]
        logger.info(f"GET /files/{file_id} request from user: {user_id}")

        # 使用服务层获取文件信息
        result = await file_service.get_file_info(user_id=user_id, file_id=file_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get file info endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {e!s}")


@router.patch("/{file_id}/public-status", response_model=StandardResponse)
async def update_file_public_status(
    file_id: str = FastAPIPath(..., description="文件ID"),
    is_public: bool = Query(description="是否设置为公开访问"),
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """更新文件的公开访问状态"""
    try:
        user_id = user_context["user_id"]
        logger.info(
            f"PATCH /files/{file_id}/public-status request from user: {user_id}"
        )

        # 使用服务层更新公开状态
        result = await file_service.update_file_public_status(
            user_id=user_id, file_id=file_id, is_public=is_public
        )

        return StandardResponse(
            success=True,
            message=f"File public status updated to: {is_public}",
            data=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update public status endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update file public status: {e!s}"
        )


@router.delete("/{file_id}", response_model=StandardResponse)
async def delete_file(
    file_id: str = FastAPIPath(..., description="文件ID"),
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """删除文件"""
    try:
        user_id = user_context["user_id"]
        logger.info(f"DELETE /files/{file_id} request from user: {user_id}")

        # 使用服务层删除文件
        result = await file_service.delete_file(user_id=user_id, file_id=file_id)

        return StandardResponse(
            success=True, message="File deleted successfully", data=result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete file endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e!s}")


# 公共访问端点（无需认证）
@router.get("/public/{file_id}", response_model=FileInfo)
async def get_public_file_info(
    file_id: str = FastAPIPath(..., description="文件ID"),
    file_service: FileService = Depends(get_file_service),
):
    """获取公共文件信息（无需认证）"""
    try:
        logger.info(f"GET /files/public/{file_id} request (public access)")

        # 使用服务层获取公共文件信息
        result = await file_service.get_public_file_info(file_id=file_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get public file info endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get public file info: {e!s}"
        )


# 管理端点
@router.get("/admin/health", response_model=dict)
async def get_storage_health(
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """获取存储后端健康状态（管理员功能）"""
    # SECURITY FIX: Add admin role validation (outside try block to avoid HTTP 500 conversion)
    if user_context.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    try:
        health_info = await file_service.get_storage_health()
        return health_info

    except Exception as e:
        logger.error(f"Error in storage health endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get storage health: {e!s}"
        )


@router.get("/admin/metrics", response_model=dict)
async def get_storage_metrics(
    user_context: dict = Depends(get_user_context),
    file_service: FileService = Depends(get_file_service),
):
    """获取存储指标（管理员功能）"""
    # SECURITY FIX: Add admin role validation (outside try block to avoid HTTP 500 conversion)
    if user_context.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    try:
        metrics = await file_service.get_storage_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error in storage metrics endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get storage metrics: {e!s}"
        )


@router.get("/user/stats", response_model=dict)
async def get_user_storage_stats(user_context: dict = Depends(get_user_context)):
    """获取用户存储统计信息"""
    try:
        user_id = user_context["user_id"]
        logger.info(f"GET /files/user/stats request from user: {user_id}")

        # 获取用户存储统计
        stats = await unified_file_db_manager.get_storage_statistics(user_id)

        return {
            "success": True,
            "data": stats,
            "message": "Storage statistics retrieved successfully",
        }

    except Exception as e:
        logger.error(f"Error in user stats endpoint: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get user statistics: {e!s}"
        )


# Note: Security logging middleware should be added to the main app, not to the router
# This is handled in unifiles.app.main.py
