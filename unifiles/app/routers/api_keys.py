"""
API 密钥管理路由模块
提供 API 密钥的 CRUD 操作和使用统计
"""

from datetime import datetime, timedelta
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

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


# ===== POST /api-keys - 创建新的API密钥 =====

@router.post("", response_model=dict)
async def create_api_key(
    name: str = Body(..., description="API密钥名称"),
    description: Optional[str] = Body(None, description="API密钥描述"),
    scopes: List[str] = Body(["read", "write"], description="权限范围"),
    max_requests_per_hour: Optional[int] = Body(1000, description="每小时最大请求数"),
    max_requests_per_day: Optional[int] = Body(10000, description="每天最大请求数"),
    max_file_size_mb: Optional[int] = Body(100, description="最大文件大小(MB)"),
    max_knowledge_bases: Optional[int] = Body(10, description="最大知识库数量"),
    expires_in_days: Optional[int] = Body(None, description="过期天数，null表示永不过期"),
    allowed_ips: Optional[List[str]] = Body(None, description="允许的IP地址列表"),
    can_create_kb: bool = Body(True, description="是否可以创建知识库"),
    can_delete_files: bool = Body(True, description="是否可以删除文件"),
    can_share_files: bool = Body(True, description="是否可以分享文件"),
    can_export_data: bool = Body(True, description="是否可以导出数据"),
    user_context: dict = Depends(get_user_context),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    创建新的API密钥

    该端点允许用户创建一个新的API密钥，并配置相关的权限和限制。
    密钥只会在创建时返回一次，之后无法恢复，请妥善保管。
    """
    try:
        user_id = user_context["user_id"]

        # 确保auth_service连接池已初始化
        await auth_service.init_connection_pool()

        # 计算过期时间
        expires_in_hours = expires_in_days * 24 if expires_in_days else None

        # 创建密钥
        result = await auth_service.create_access_token(
            user_id=user_id,
            name=name,
            description=description,
            expires_in_hours=expires_in_hours,
            scopes=scopes,
            max_requests_per_hour=max_requests_per_hour,
            max_requests_per_day=max_requests_per_day,
            max_file_size_mb=max_file_size_mb,
            max_knowledge_bases=max_knowledge_bases,
            can_create_kb=can_create_kb,
            can_delete_files=can_delete_files,
            can_share_files=can_share_files,
            can_export_data=can_export_data,
            allowed_ips=allowed_ips,
        )

        logger.info(f"API key '{name}' created for user {user_id}")

        return {
            "success": True,
            "message": "API key created successfully. Please save it securely as it won't be shown again.",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create API key: {str(e)}")


# ===== GET /api-keys - 列出所有API密钥 =====

@router.get("", response_model=dict)
async def list_api_keys(
    user_context: dict = Depends(get_user_context),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    列出用户的所有API密钥

    返回当前用户的所有API密钥列表（不包含实际密钥值），
    包含使用统计和状态信息。
    """
    try:
        user_id = user_context["user_id"]

        # 确保auth_service连接池已初始化
        await auth_service.init_connection_pool()

        # 获取用户的所有密钥
        keys = await auth_service.get_user_tokens(user_id)

        logger.debug(f"Retrieved {len(keys)} API keys for user {user_id}")

        return {
            "success": True,
            "data": {
                "api_keys": keys,
                "total": len(keys),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list API keys: {str(e)}")


# ===== GET /api-keys/{key_id} - 获取单个API密钥详情 =====

@router.get("/{key_id}", response_model=dict)
async def get_api_key(
    key_id: str,
    user_context: dict = Depends(get_user_context),
):
    """
    获取单个API密钥的详细信息

    返回指定API密钥的详细配置和使用统计（不包含实际密钥值）。
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
                # 验证所有权并获取密钥信息
                query = """
                    SELECT id, name, description, scopes, is_active,
                           total_requests, requests_today, requests_this_hour,
                           max_requests_per_hour, max_requests_per_day,
                           max_file_size_mb, max_knowledge_bases,
                           can_create_kb, can_delete_files, can_share_files, can_export_data,
                           allowed_ips, created_at, expires_at, last_used_at,
                           expiry_status, hourly_usage_percent, daily_usage_percent
                    FROM unifiles.access_keys_overview
                    WHERE id = $1 AND user_id = $2
                """
                key_info = await conn.fetchrow(query, key_id, user_id)

                if not key_info:
                    raise HTTPException(status_code=404, detail="API key not found")

                return {
                    "success": True,
                    "data": dict(key_info)
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get API key: {str(e)}")


# ===== PATCH /api-keys/{key_id} - 更新API密钥配置 =====

@router.patch("/{key_id}", response_model=dict)
async def update_api_key(
    key_id: str,
    name: Optional[str] = Body(None, description="API密钥名称"),
    description: Optional[str] = Body(None, description="API密钥描述"),
    is_active: Optional[bool] = Body(None, description="是否启用"),
    max_requests_per_hour: Optional[int] = Body(None, description="每小时最大请求数"),
    max_requests_per_day: Optional[int] = Body(None, description="每天最大请求数"),
    max_file_size_mb: Optional[int] = Body(None, description="最大文件大小(MB)"),
    max_knowledge_bases: Optional[int] = Body(None, description="最大知识库数量"),
    can_create_kb: Optional[bool] = Body(None, description="是否可以创建知识库"),
    can_delete_files: Optional[bool] = Body(None, description="是否可以删除文件"),
    can_share_files: Optional[bool] = Body(None, description="是否可以分享文件"),
    can_export_data: Optional[bool] = Body(None, description="是否可以导出数据"),
    user_context: dict = Depends(get_user_context),
):
    """
    更新API密钥配置

    允许修改API密钥的各项配置，如权限、限制等。
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

        # 构建更新配置对象
        config = {}
        if name is not None:
            config["name"] = name
        if description is not None:
            config["description"] = description
        if is_active is not None:
            config["is_active"] = is_active
        if max_requests_per_hour is not None:
            config["max_requests_per_hour"] = max_requests_per_hour
        if max_requests_per_day is not None:
            config["max_requests_per_day"] = max_requests_per_day
        if max_file_size_mb is not None:
            config["max_file_size_mb"] = max_file_size_mb
        if max_knowledge_bases is not None:
            config["max_knowledge_bases"] = max_knowledge_bases
        if can_create_kb is not None:
            config["can_create_kb"] = can_create_kb
        if can_delete_files is not None:
            config["can_delete_files"] = can_delete_files
        if can_share_files is not None:
            config["can_share_files"] = can_share_files
        if can_export_data is not None:
            config["can_export_data"] = can_export_data

        if not config:
            raise HTTPException(status_code=400, detail="No fields to update")

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                # 验证所有权
                verify_query = "SELECT user_id FROM unifiles.access_keys WHERE id = $1"
                key_owner = await conn.fetchval(verify_query, key_id)

                if not key_owner:
                    raise HTTPException(status_code=404, detail="API key not found")

                if key_owner != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")

                # 调用update_access_key_config函数
                result = await conn.fetchval(
                    "SELECT update_access_key_config($1, $2)",
                    key_id,
                    json.dumps(config)
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to update API key")
                    raise HTTPException(status_code=500, detail=error_msg)

                logger.info(f"API key {key_id} updated by user {user_id}")

                return {
                    "success": True,
                    "message": "API key updated successfully"
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")


# ===== DELETE /api-keys/{key_id} - 撤销API密钥 =====

@router.delete("/{key_id}", response_model=StandardResponse)
async def revoke_api_key(
    key_id: str,
    user_context: dict = Depends(get_user_context),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    撤销（停用）API密钥

    将指定的API密钥标记为不活动状态，撤销后该密钥将无法再使用。
    """
    try:
        user_id = user_context["user_id"]

        # 确保auth_service连接池已初始化
        await auth_service.init_connection_pool()

        # 撤销密钥
        success = await auth_service.revoke_token(key_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="API key not found or already revoked")

        logger.info(f"API key {key_id} revoked by user {user_id}")

        return StandardResponse(
            success=True,
            message="API key revoked successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke API key: {str(e)}")


# ===== GET /api-keys/{key_id}/stats - 查看密钥使用统计 =====

@router.get("/{key_id}/stats", response_model=dict)
async def get_api_key_stats(
    key_id: str,
    days: int = 30,
    user_context: dict = Depends(get_user_context),
):
    """
    查看API密钥的使用统计

    返回指定API密钥的详细使用统计，包括历史使用记录。
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
                key_info = await conn.fetchrow(
                    "SELECT * FROM unifiles.access_keys WHERE id = $1 AND user_id = $2",
                    key_id, user_id
                )

                if not key_info:
                    raise HTTPException(status_code=404, detail="API key not found")

                # 获取使用统计（最近N天）
                usage_stats = await conn.fetch(
                    """
                    SELECT metric_date, api_calls, files_uploaded,
                           bandwidth_bytes_out, requests_by_endpoint
                    FROM unifiles.usage_metrics
                    WHERE access_key_id = $1
                      AND metric_date >= CURRENT_DATE - $2
                      AND metric_hour IS NULL
                    ORDER BY metric_date DESC
                    """,
                    key_id, days
                )

                return {
                    "success": True,
                    "data": {
                        "key_info": {
                            "key_id": key_info["id"],
                            "name": key_info["name"],
                            "total_requests": key_info["total_requests"],
                            "last_used_at": key_info["last_used_at"].isoformat() if key_info["last_used_at"] else None,
                        },
                        "usage_history": [dict(row) for row in usage_stats],
                        "period_days": days
                    }
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get API key stats: {str(e)}")
