"""
使用量查询路由模块
提供API使用统计、配额查询等功能
"""

from datetime import date, datetime, timedelta
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from unifiles.config import settings
from unifiles.core.services import AuthService


# ===== 依赖注入辅助函数 =====

def get_auth_service() -> AuthService:
    """获取认证服务实例"""
    # Create pg_config dict from settings
    pg_config = {
        "host": settings.database.host,
        "port": settings.database.port,
        "database": settings.database.database,
        "user": settings.database.user,
        "password": settings.database.password,
    }
    return AuthService(pg_config)


async def get_user_context(
    request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """提取用户上下文"""
    return await auth_service.extract_user_from_request(request)


# ===== 创建路由器 =====

router = APIRouter(prefix="/usage", tags=["Usage"])


# ===== GET /usage/stats - 获取使用统计 =====

@router.get("/stats", response_model=dict)
async def get_usage_stats(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    user_context: dict = Depends(get_user_context),
):
    """
    获取用户的使用统计

    返回指定日期范围内的使用统计数据，包括总计和每日明细。
    """
    try:
        import json

        user_id = user_context["user_id"]

        # 解析日期
        start_date_obj = (
            datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date.today() - timedelta(days=30)
        )
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()

        # Create pg_config dict from settings
        pg_config = {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "user": settings.database.user,
            "password": settings.database.password,
        }

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                # 调用数据库函数获取使用统计
                result = await conn.fetchval(
                    "SELECT get_user_usage_stats($1, $2, $3)",
                    user_id,
                    start_date_obj,
                    end_date_obj
                )

                stats = json.loads(result)

                return {
                    "success": True,
                    "data": stats
                }

    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get usage stats: {str(e)}")


# ===== GET /usage/quota - 获取配额信息 =====

@router.get("/quota", response_model=dict)
async def get_quota_info(
    user_context: dict = Depends(get_user_context),
):
    """
    获取用户当前的配额信息

    返回各项资源的配额限制和当前使用情况。
    """
    try:
        import json

        user_id = user_context["user_id"]

        # Create pg_config dict from settings
        pg_config = {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "user": settings.database.user,
            "password": settings.database.password,
        }

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                # 检查各项配额
                api_calls_quota = await conn.fetchval(
                    "SELECT check_user_quota($1, $2, $3)",
                    user_id, "api_calls", 0
                )
                storage_quota = await conn.fetchval(
                    "SELECT check_user_quota($1, $2, $3)",
                    user_id, "storage", 0
                )
                files_quota = await conn.fetchval(
                    "SELECT check_user_quota($1, $2, $3)",
                    user_id, "files_upload", 0
                )

                return {
                    "success": True,
                    "data": {
                        "api_calls": json.loads(api_calls_quota),
                        "storage": json.loads(storage_quota),
                        "files": json.loads(files_quota)
                    }
                }

    except Exception as e:
        logger.error(f"Error getting quota info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get quota info: {str(e)}")
