"""
用户数据库管理器
专注用户的CRUD和存在性检查，供其他管理器复用
"""

import json
from typing import Optional

from loguru import logger

from .base_manager import BaseDBManager
from .models import UserModel


class UserDBManager(BaseDBManager):
    """用户数据库管理器 - 处理用户的创建、查询和校验"""

    async def create_user(self, user_model: UserModel) -> UserModel:
        """创建用户"""
        async with await self.get_connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO unifiles.users (
                            id, username, email, display_name,
                            user_status, user_role, knowledge_ids, user_settings
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        user_model.id,
                        user_model.username,
                        user_model.email,
                        user_model.display_name,
                        user_model.user_status,
                        user_model.user_role,
                        user_model.knowledge_ids,
                        json.dumps(user_model.user_settings),
                    )

                    # 获取创建的用户信息
                    result = await conn.fetchrow(
                        "SELECT * FROM unifiles.users WHERE id = $1", user_model.id
                    )

                    if result:
                        user_model.created_at = result["created_at"]
                        user_model.updated_at = result["updated_at"]

                    logger.info(f"User created: {user_model.id}")
                    return user_model

            except Exception as e:
                logger.error(f"Error creating user {user_model.id}: {e}")
                raise

    async def get_user(self, user_id: str) -> Optional[UserModel]:
        """获取用户信息"""
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.users WHERE id = $1", user_id
                )

                if result:
                    return UserModel(
                        id=result["id"],
                        username=result.get("username"),
                        email=result.get("email"),
                        display_name=result.get("display_name"),
                        user_status=result.get("user_status", "active"),
                        user_role=result.get("user_role", "user"),
                        knowledge_ids=list(result.get("knowledge_ids", [])),
                        user_settings=json.loads(result.get("user_settings") or "{}"),
                        created_at=result["created_at"],
                        updated_at=result.get("updated_at"),
                        last_login_at=result.get("last_login_at"),
                    )
                return None

            except Exception as e:
                logger.error(f"Error getting user {user_id}: {e}")
                raise

    async def ensure_user_exists(self, user_id: str) -> UserModel:
        """确保用户存在，不存在则创建"""
        user = await self.get_user(user_id)
        if not user:
            user = UserModel(id=user_id)
            user = await self.create_user(user)
        return user


# 全局实例
unified_user_db_manager = UserDBManager()

