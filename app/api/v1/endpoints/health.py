from fastapi import APIRouter
from app.models.responses import HealthResponse, SupportedFileTypesResponse
from utils import get_supported_file_types

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(status="ok", message="Service is healthy")


@router.get("/supported-file-types", response_model=SupportedFileTypesResponse)
async def get_supported_file_types_endpoint():
    """获取支持的文件类型"""
    file_types = get_supported_file_types()
    return SupportedFileTypesResponse(
        status="ok",
        message="Supported file types",
        data={"supported_file_types": file_types["all_supported"]}
    )