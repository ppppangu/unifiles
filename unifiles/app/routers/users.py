"""
用户管理路由
处理用户相关的API请求
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from unifiles.app.schemas import (
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
        existing_user = await unified_db_manager.users.get_user(
            user_request.user_id
        )
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
        error_msg = f"Error creating user {user_request.user_id}: {type(e).__name__}: {e}"
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
