"""
用户管理路由
处理用户相关的API请求
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

logger.bind(service="unifiles-v1")

from unifiles.app.schemas import (
    AccessKeyCreateRequest,
    AccessKeyCreateResponse,
    AccessKeyInfo,
    AccessKeyListResponse,
    StandardResponse,
    UserCreateRequest,
    UserCreateResponse,
    UserInfo,
)
from unifiles.core.database import unified_db_manager
from unifiles.core.database.models import UserModel

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/create", response_model=UserCreateResponse)
async def create_user(user_request: UserCreateRequest):
    """
    创建新用户

    此端点不需要认证，可以直接创建用户账户。

    Args:
        user_request: 用户创建请求数据

    Returns:
        UserCreateResponse: 包含创建的用户信息

    Raises:
        HTTPException: 当用户创建失败时
    """
    try:
        logger.info(f"Creating user: {user_request.user_id}")

        # 检查用户是否已存在
        existing_user = await unified_db_manager.users.get_user(user_request.user_id)
        if existing_user:
            logger.warning(f"User already exists: {user_request.user_id}")
            raise HTTPException(
                status_code=409,
                detail=f"User with ID '{user_request.user_id}' already exists",
            )

        # 创建用户模型
        user_model = UserModel(
            id=user_request.user_id,
            username=user_request.username,
            email=user_request.email,
            display_name=user_request.display_name,
            user_settings=user_request.user_settings or {},
            knowledge_ids=[],
        )

        # 创建用户
        created_user = await unified_db_manager.users.create_user(user_model)

        # 构造响应
        user_info = UserInfo(
            id=created_user.id,
            username=created_user.username,
            email=created_user.email,
            display_name=created_user.display_name,
            user_status=created_user.user_status,
            user_role=created_user.user_role,
            knowledge_ids=created_user.knowledge_ids,
            user_settings=created_user.user_settings,
            created_at=(
                created_user.created_at.isoformat() if created_user.created_at else None
            ),
            updated_at=(
                created_user.updated_at.isoformat() if created_user.updated_at else None
            ),
            last_login_at=(
                created_user.last_login_at.isoformat()
                if created_user.last_login_at
                else None
            ),
        )

        logger.info(f"User created successfully: {created_user.id}")

        return UserCreateResponse(
            success=True, message="User created successfully", user=user_info
        )

    except HTTPException as http_exc:
        # 重新抛出HTTPException
        raise http_exc from None
    except Exception as e:
        error_msg = (
            f"Error creating user {user_request.user_id}: {type(e).__name__}: {e}"
        )
        logger.error(error_msg)
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create user: {type(e).__name__}: {e!s}",
        ) from e


@router.get("/{user_id}", response_model=StandardResponse)
async def get_user(user_id: str):
    """
    获取用户信息

    此端点不需要认证。

    Args:
        user_id: 用户ID

    Returns:
        StandardResponse: 包含用户信息

    Raises:
        HTTPException: 当用户不存在或获取失败时
    """
    try:
        logger.info(f"Getting user: {user_id}")

        # 获取用户信息
        user = await unified_db_manager.users.get_user(user_id)

        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        # 构造响应
        user_info = UserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            user_status=user.user_status,
            user_role=user.user_role,
            knowledge_ids=user.knowledge_ids,
            user_settings=user.user_settings,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None,
            last_login_at=(
                user.last_login_at.isoformat() if user.last_login_at else None
            ),
        )

        logger.info(f"User retrieved successfully: {user_id}")

        return StandardResponse(
            success=True,
            message="User retrieved successfully",
            data=user_info.model_dump(),
        )

    except HTTPException as http_exc:
        # 重新抛出HTTPException
        raise http_exc from None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user: {e!s}",
        ) from e


@router.post("/login", response_model=StandardResponse)
async def login_user(email: str):
    """
    用户登录 - 通过邮箱获取用户信息

    此端点不需要认证。

    Args:
        email: 用户邮箱

    Returns:

        StandardResponse: 包含用户信息

    Raises:
        HTTPException: 当用户不存在或登录失败时
    """
    try:
        logger.info(f"User login attempt: {email}")

        # 通过邮箱查询用户
        result = await unified_db_manager.users.fetch_one(
            "SELECT * FROM unifiles.users WHERE email = $1", email, operation="login"
        )

        logger.info(f"User login result: {result}") 

        if not result:
            logger.warning(f"User not found for email: {email}")
            raise HTTPException(
                status_code=404, detail=f"User with email '{email}' not found"
            )

        # 构造用户信息响应
        # 处理 user_settings：如果是字符串则解析为字典
        user_settings = result.get("user_settings") or {}
        if isinstance(user_settings, str):
            try:
                user_settings = json.loads(user_settings)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"Failed to parse user_settings as JSON: {user_settings}")
                user_settings = {}

        user_info = UserInfo(
            id=result["id"],
            username=result.get("username"),
            email=result.get("email"),
            display_name=result.get("display_name"),
            user_status=result.get("user_status", "active"),
            user_role=result.get("user_role", "user"),
            knowledge_ids=result.get("knowledge_ids") or [],
            user_settings=user_settings,
            created_at=result["created_at"].isoformat()
            if result.get("created_at")
            else None,
            updated_at=result["updated_at"].isoformat()
            if result.get("updated_at")
            else None,
            last_login_at=(
                result["last_login_at"].isoformat()
                if result.get("last_login_at")
                else None
            ),
        )

        logger.info(f"User login successful: {email}")

        return StandardResponse(
            success=True,
            message="Login successful",
            data=user_info.model_dump(),
        )

    except HTTPException as http_exc:
        raise http_exc from None
    except Exception as e:
        logger.error(f"Error during login for {email}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {e!s}",
        ) from e


@router.post("/{user_id}/access-keys", response_model=AccessKeyCreateResponse)
async def create_user_access_key(user_id: str, body: AccessKeyCreateRequest):
    """
    为指定用户创建访问密钥（API Key）

    调用数据库函数 `create_access_key` 生成密钥并返回。
    """
    try:
        # 1) 校验用户是否存在
        user = await unified_db_manager.users.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        # 2) 处理可选参数与默认权限范围
        scopes = body.scopes or ["read", "write"]
        description = body.description
        expires_at = body.expires_at  # RFC3339字符串或None

        # 3) 调用数据库函数创建Access Key
        #    函数签名：create_access_key(
        #      p_user_id TEXT,
        #      p_name TEXT,
        #      p_description TEXT DEFAULT NULL,
        #      p_scopes TEXT[] DEFAULT '{"read", "write"}',
        #      p_expires_at TIMESTAMPTZ DEFAULT NULL,
        #      ... 其余参数使用默认值
        #    ) RETURNS JSONB
        result = await unified_db_manager.users.fetch_value(
            "SELECT create_access_key($1, $2, $3, $4, $5)",
            user_id,
            body.name,
            description,
            scopes,
            expires_at,
        )

        # 4) 解析结果
        if not isinstance(result, dict):
            # 兼容性处理：某些驱动可能返回JSON字符串
            try:
                import json

                result = json.loads(result)
            except Exception:
                logger.error("Unexpected result type from create_access_key")
                raise HTTPException(status_code=500, detail="Key creation failed")

        if result.get("success") is True:
            return AccessKeyCreateResponse(
                success=True,
                message=result.get("message", "Access key created successfully"),
                key_id=result.get("key_id"),
                access_key=result.get("access_key"),
            )

        # 非成功，按错误类型映射HTTP状态码
        err = result.get("error")
        msg = result.get("message", "Failed to create access key")
        if err == "user_not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating access key for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Key creation error: {e!s}") from e


@router.get("/{user_id}/access-keys", response_model=AccessKeyListResponse)
async def list_user_access_keys(user_id: str, active: Optional[bool] = None):
    """
    获取指定用户的访问密钥列表

    可选按是否启用过滤。
    """
    try:
        # 确认用户是否存在
        user = await unified_db_manager.users.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        # 组装查询
        base_sql = (
            "SELECT id, name, description, scopes, is_active, created_at, "
            "expires_at, last_used_at FROM unifiles.access_keys WHERE user_id = $1"
        )
        params = [user_id]
        if active is True:
            base_sql += " AND is_active = TRUE"
        elif active is False:
            base_sql += " AND is_active = FALSE"
        base_sql += " ORDER BY created_at DESC"

        rows = await unified_db_manager.users.fetch_many(base_sql, *params)

        access_keys: List[AccessKeyInfo] = []
        for r in rows:
            access_keys.append(
                AccessKeyInfo(
                    id=r["id"],
                    name=r.get("name", ""),
                    description=r.get("description"),
                    scopes=list(r.get("scopes") or []),
                    is_active=bool(r.get("is_active", True)),
                    created_at=r["created_at"].isoformat() if r.get("created_at") else "",
                    expires_at=r["expires_at"].isoformat() if r.get("expires_at") else None,
                    last_used_at=r["last_used_at"].isoformat() if r.get("last_used_at") else None,
                )
            )

        return AccessKeyListResponse(
            success=True,
            message="Access keys retrieved successfully",
            access_keys=access_keys,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing access keys for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list access keys: {e!s}") from e
