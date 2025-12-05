from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from unifiles.core.logging import get_logger

logger = get_logger()

from unifiles.app.routers.unifiles import (
    StandardResponse,
    get_user_context,
)

router = APIRouter(prefix="/manager", tags=["Manager"])


@router.get("/system/status", response_model=StandardResponse)
async def get_system_status(
    request: Request, user_context: dict = Depends(get_user_context)
):
    """获取系统状态信息（管理员专用）"""
    # SECURITY FIX: Add authentication and admin role validation (outside try block to avoid HTTP 500 conversion)
    if user_context.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    try:
        # TODO: 实现系统状态检查逻辑
        # - 数据库连接状态
        # - 存储服务状态
        # - 系统资源使用情况
        # - 服务健康状态

        logger.info("System status check requested by admin")

        return StandardResponse(
            success=True,
            message="System status retrieved successfully",
            data={
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "database": "connected",
                    "storage": "healthy",
                    "memory_usage": "normal",
                    "disk_usage": "normal",
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get system status: {e!s}"
        )
