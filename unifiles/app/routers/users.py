"""
用户管理路由
处理用户相关的API请求
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger

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

logger = logger.bind(service="unifiles-v1")

router = APIRouter(prefix="/users", tags=["Users"])


def _user_model_to_info(user: UserModel) -> UserInfo:
    """将用户模型转换为API响应模型"""
    return UserInfo(
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
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


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
        user_info = _user_model_to_info(created_user)

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
        user_info = _user_model_to_info(user)

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
        user = await unified_db_manager.users.get_user_by_email(email)

        if not user:
            logger.warning(f"User not found for email: {email}")
            raise HTTPException(
                status_code=404, detail=f"User with email '{email}' not found"
            )

        # 构造用户信息响应
        user_info = _user_model_to_info(user)

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

        # 2) 调用数据库管理器创建 Access Key
        result = await unified_db_manager.users.create_access_key(
            user_id=user_id,
            name=body.name,
            description=body.description,
            scopes=body.scopes,
            expires_at=body.expires_at,
        )

        # 3) 处理结果
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

        # 调用数据库管理器获取密钥列表
        rows = await unified_db_manager.users.list_access_keys(user_id, active=active)

        # 构造响应
        access_keys: List[AccessKeyInfo] = []
        for r in rows:
            access_keys.append(
                AccessKeyInfo(
                    id=r["id"],
                    name=r.get("name", ""),
                    description=r.get("description"),
                    scopes=list(r.get("scopes") or []),
                    is_active=bool(r.get("is_active", True)),
                    created_at=r["created_at"].isoformat()
                    if r.get("created_at")
                    else "",
                    expires_at=r["expires_at"].isoformat()
                    if r.get("expires_at")
                    else None,
                    last_used_at=r["last_used_at"].isoformat()
                    if r.get("last_used_at")
                    else None,
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
        raise HTTPException(
            status_code=500, detail=f"Failed to list access keys: {e!s}"
        ) from e


@router.delete("/{user_id}/access-keys/{key_id}", response_model=StandardResponse)
async def delete_user_access_key(user_id: str, key_id: str):
    """
    删除（撤销）指定用户的访问密钥

    实际执行软删除，将密钥标记为不活跃状态。

    Args:
        user_id: 用户ID
        key_id: 访问密钥ID

    Returns:
        StandardResponse: 删除操作结果

    Raises:
        HTTPException: 当用户不存在、密钥不存在或删除失败时
    """
    try:
        logger.info(f"Deleting access key {key_id} for user {user_id}")

        # 1) 验证用户是否存在
        user = await unified_db_manager.users.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

        # 2) 验证密钥是否属于该用户
        key_info = await unified_db_manager.users.get_access_key(key_id)

        if not key_info:
            raise HTTPException(
                status_code=404, detail=f"Access key '{key_id}' not found"
            )

        if key_info["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail=f"Access key '{key_id}' does not belong to user '{user_id}'",
            )

        # 3) 调用数据库管理器撤销密钥（软删除）
        result = await unified_db_manager.users.revoke_access_key(key_id)

        # 4) 处理结果
        if result.get("success") is True:
            logger.info(f"Access key {key_id} deleted successfully")
            return StandardResponse(
                success=True,
                message="Access key deleted successfully",
                data={"key_id": key_id},
            )

        # 删除失败
        err = result.get("error")
        msg = result.get("message", "Failed to delete access key")
        if err == "key_not_found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting access key {key_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete access key: {e!s}"
        ) from e
