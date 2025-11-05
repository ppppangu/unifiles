"""
订阅管理路由模块
提供订阅套餐查询、订阅管理等功能
"""

from typing import Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from loguru import logger

from unifiles.server.schemas import StandardResponse
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

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ===== GET /subscriptions/plans - 列出所有可用套餐 =====

@router.get("/plans", response_model=dict)
async def list_subscription_plans():
    """
    列出所有可用的订阅套餐

    返回所有公开的、活跃的订阅套餐列表，包含定价和功能信息。
    """
    try:
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
                query = """
                    SELECT id, plan_name, plan_type, display_name, description,
                           max_files_per_month, max_storage_gb, max_api_calls_per_month,
                           max_file_size_mb, max_knowledge_bases, max_api_keys,
                           rate_limit_per_hour, rate_limit_per_day,
                           features, price_monthly_usd, price_yearly_usd, currency,
                           sort_order
                    FROM unifiles.subscription_plans
                    WHERE is_active = TRUE AND is_public = TRUE
                    ORDER BY sort_order ASC
                """
                results = await conn.fetch(query)

                plans = [dict(row) for row in results]

                return {
                    "success": True,
                    "data": {
                        "plans": plans,
                        "total": len(plans)
                    }
                }

    except Exception as e:
        logger.error(f"Error listing subscription plans: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list subscription plans: {str(e)}")


# ===== GET /subscriptions/my-subscription - 获取当前用户订阅 =====

@router.get("/my-subscription", response_model=dict)
async def get_my_subscription(user_context: dict = Depends(get_user_context)):
    """
    获取当前用户的订阅信息

    返回用户当前的活跃订阅，包括套餐详情和使用情况。
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
                # 调用数据库函数获取用户订阅
                result = await conn.fetchval(
                    "SELECT get_user_active_subscription($1)",
                    user_id
                )

                subscription_data = json.loads(result)

                return {
                    "success": True,
                    "data": subscription_data
                }

    except Exception as e:
        logger.error(f"Error getting user subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get subscription: {str(e)}")


# ===== POST /subscriptions/create - 创建订阅 =====

@router.post("/create", response_model=dict)
async def create_subscription(
    plan_id: str = Body(..., description="套餐ID"),
    billing_cycle: str = Body("monthly", description="计费周期: monthly, yearly, lifetime"),
    user_context: dict = Depends(get_user_context),
):
    """
    创建新订阅

    为当前用户创建新的订阅。注意：实际的支付流程需要集成 Stripe。
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
                # 调用数据库函数创建订阅
                result = await conn.fetchval(
                    "SELECT create_subscription($1, $2, $3)",
                    user_id,
                    plan_id,
                    billing_cycle
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to create subscription")
                    raise HTTPException(status_code=400, detail=error_msg)

                logger.info(f"Subscription created for user {user_id}, plan {plan_id}")

                return {
                    "success": True,
                    "message": "Subscription created successfully",
                    "data": result_dict
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")


# ===== POST /subscriptions/cancel - 取消订阅 =====

@router.post("/cancel", response_model=StandardResponse)
async def cancel_subscription(
    subscription_id: str = Body(..., description="订阅ID"),
    reason: Optional[str] = Body(None, description="取消原因"),
    immediate: bool = Body(False, description="是否立即取消"),
    user_context: dict = Depends(get_user_context),
):
    """
    取消订阅

    取消指定的订阅。immediate=False 时在当前周期结束后取消，immediate=True 时立即取消。
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
                # 验证订阅所有权
                owner_query = """
                    SELECT user_id FROM unifiles.user_subscriptions WHERE id = $1
                """
                owner_id = await conn.fetchval(owner_query, subscription_id)

                if not owner_id:
                    raise HTTPException(status_code=404, detail="Subscription not found")

                if owner_id != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

                # 调用数据库函数取消订阅
                result = await conn.fetchval(
                    "SELECT cancel_subscription($1, $2, $3)",
                    subscription_id,
                    reason,
                    immediate
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to cancel subscription")
                    raise HTTPException(status_code=400, detail=error_msg)

                logger.info(f"Subscription {subscription_id} cancelled by user {user_id}")

                return StandardResponse(
                    success=True,
                    message="Subscription cancelled successfully"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


# ===== GET /subscriptions/history - 获取订阅历史 =====

@router.get("/history", response_model=dict)
async def get_subscription_history(
    user_context: dict = Depends(get_user_context),
):
    """
    获取订阅历史

    返回用户的所有订阅变更历史记录。
    """
    try:
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
                query = """
                    SELECT sh.*,
                           fp.plan_name as from_plan_name,
                           tp.plan_name as to_plan_name
                    FROM unifiles.subscription_history sh
                    LEFT JOIN unifiles.subscription_plans fp ON sh.from_plan_id = fp.id
                    LEFT JOIN unifiles.subscription_plans tp ON sh.to_plan_id = tp.id
                    WHERE sh.user_id = $1
                    ORDER BY sh.created_at DESC
                """
                results = await conn.fetch(query, user_id)

                history = [dict(row) for row in results]

                return {
                    "success": True,
                    "data": {
                        "history": history,
                        "total": len(history)
                    }
                }

    except Exception as e:
        logger.error(f"Error getting subscription history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get subscription history: {str(e)}")
