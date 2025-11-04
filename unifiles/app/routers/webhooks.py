"""
Webhook 管理路由模块
提供 Webhook 端点的 CRUD 操作和事件查询
"""

from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from loguru import logger

from unifiles.app.schemas import StandardResponse
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

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ===== POST /webhooks - 创建 Webhook =====

@router.post("", response_model=dict)
async def create_webhook(
    url: str = Body(..., description="Webhook URL"),
    events: List[str] = Body(..., description="订阅的事件类型列表"),
    description: Optional[str] = Body(None, description="Webhook 描述"),
    timeout_seconds: int = Body(30, description="超时时间（秒）"),
    user_context: dict = Depends(get_user_context),
):
    """
    创建新的 Webhook 端点

    创建一个新的 Webhook，用于接收指定类型的事件通知。
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
                # 调用数据库函数创建 Webhook
                result = await conn.fetchval(
                    "SELECT create_webhook_endpoint($1, $2, $3, $4, $5)",
                    user_id, url, events, description, timeout_seconds
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to create webhook")
                    raise HTTPException(status_code=400, detail=error_msg)

                logger.info(f"Webhook created for user {user_id}: {url}")

                return {
                    "success": True,
                    "message": "Webhook created successfully. Please save the secret_key securely.",
                    "data": result_dict
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")


# ===== GET /webhooks - 列出所有 Webhooks =====

@router.get("", response_model=dict)
async def list_webhooks(
    user_context: dict = Depends(get_user_context),
):
    """
    列出用户的所有 Webhook

    返回用户创建的所有 Webhook 端点列表（不包含 secret_key）。
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
                    SELECT id, url, events, description, is_active, status,
                           failure_count, last_failure_at, last_success_at,
                           timeout_seconds, created_at, updated_at
                    FROM unifiles.webhook_endpoints
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """
                results = await conn.fetch(query, user_id)

                webhooks = [dict(row) for row in results]

                return {
                    "success": True,
                    "data": {
                        "webhooks": webhooks,
                        "total": len(webhooks)
                    }
                }

    except Exception as e:
        logger.error(f"Error listing webhooks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")


# ===== DELETE /webhooks/{webhook_id} - 删除 Webhook =====

@router.delete("/{webhook_id}", response_model=StandardResponse)
async def delete_webhook(
    webhook_id: str,
    user_context: dict = Depends(get_user_context),
):
    """
    删除 Webhook 端点

    删除指定的 Webhook 端点。
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
                # 验证所有权并删除
                result = await conn.execute(
                    """
                    DELETE FROM unifiles.webhook_endpoints
                    WHERE id = $1 AND user_id = $2
                    """,
                    webhook_id, user_id
                )

                if "DELETE 0" in result:
                    raise HTTPException(status_code=404, detail="Webhook not found")

                logger.info(f"Webhook {webhook_id} deleted by user {user_id}")

                return StandardResponse(
                    success=True,
                    message="Webhook deleted successfully"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete webhook: {str(e)}")


# ===== GET /webhooks/{webhook_id}/events - 查看 Webhook 事件 =====

@router.get("/{webhook_id}/events", response_model=dict)
async def get_webhook_events(
    webhook_id: str,
    limit: int = 100,
    user_context: dict = Depends(get_user_context),
):
    """
    查看 Webhook 的事件历史

    返回指定 Webhook 的事件发送历史。
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
                # 验证所有权
                webhook_owner = await conn.fetchval(
                    "SELECT user_id FROM unifiles.webhook_endpoints WHERE id = $1",
                    webhook_id
                )

                if not webhook_owner:
                    raise HTTPException(status_code=404, detail="Webhook not found")

                if webhook_owner != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

                # 获取事件历史
                query = """
                    SELECT id, event_type, status, attempts,
                           last_attempt_at, response_code, error_message,
                           created_at, completed_at
                    FROM unifiles.webhook_events
                    WHERE webhook_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """
                results = await conn.fetch(query, webhook_id, limit)

                events = [dict(row) for row in results]

                return {
                    "success": True,
                    "data": {
                        "events": events,
                        "total": len(events)
                    }
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get webhook events: {str(e)}")
