"""
用户数据库管理器
专注用户的CRUD和存在性检查，供其他管理器复用
"""

import json
from typing import Optional

from unifiles.core.logging import get_logger

logger = get_logger()

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

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """通过邮箱获取用户信息"""
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT * FROM unifiles.users WHERE email = $1", email
                )

                if result:
                    # 处理 user_settings：如果是字符串则解析为字典
                    user_settings = result.get("user_settings") or {}
                    if isinstance(user_settings, str):
                        try:
                            user_settings = json.loads(user_settings)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning(
                                f"Failed to parse user_settings as JSON: {user_settings}"
                            )
                            user_settings = {}

                    return UserModel(
                        id=result["id"],
                        username=result.get("username"),
                        email=result.get("email"),
                        display_name=result.get("display_name"),
                        user_status=result.get("user_status", "active"),
                        user_role=result.get("user_role", "user"),
                        knowledge_ids=list(result.get("knowledge_ids", [])),
                        user_settings=user_settings,
                        created_at=result["created_at"],
                        updated_at=result.get("updated_at"),
                        last_login_at=result.get("last_login_at"),
                    )
                return None

            except Exception as e:
                logger.error(f"Error getting user by email {email}: {e}")
                raise

    async def ensure_user_exists(self, user_id: str) -> UserModel:
        """确保用户存在，不存在则创建"""
        user = await self.get_user(user_id)
        if not user:
            user = UserModel(id=user_id)
            user = await self.create_user(user)
        return user

    # ==================== Access Key 管理方法 ====================

    async def create_access_key(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        scopes: Optional[list] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        """
        创建访问密钥

        Args:
            user_id: 用户ID
            name: 密钥名称
            description: 密钥描述
            scopes: 权限范围列表
            expires_at: 过期时间（RFC3339字符串）

        Returns:
            包含创建结果的字典
        """
        async with await self.get_connection() as conn:
            try:
                # 设置默认权限
                if scopes is None:
                    scopes = ["read", "write"]

                # 调用数据库函数
                result = await conn.fetchval(
                    "SELECT create_access_key($1, $2, $3, $4, $5)",
                    user_id,
                    name,
                    description,
                    scopes,
                    expires_at,
                )

                # 解析 JSONB 结果
                if not isinstance(result, dict):
                    try:
                        result = json.loads(result)
                    except (json.JSONDecodeError, ValueError):
                        logger.error("Failed to parse create_access_key result")
                        return {
                            "success": False,
                            "error": "parse_error",
                            "message": "Failed to parse database response",
                        }

                return result

            except Exception as e:
                logger.error(f"Error creating access key for user {user_id}: {e}")
                raise

    async def list_access_keys(
        self, user_id: str, active: Optional[bool] = None
    ) -> list:
        """
        获取用户的访问密钥列表

        Args:
            user_id: 用户ID
            active: 是否只返回活跃的密钥（None=全部，True=活跃，False=非活跃）

        Returns:
            访问密钥字典列表
        """
        async with await self.get_connection() as conn:
            try:
                # 构建查询
                base_sql = (
                    "SELECT id, name, description, scopes, is_active, created_at, "
                    "expires_at, last_used_at FROM unifiles.access_keys WHERE user_id = $1"
                )

                if active is True:
                    base_sql += " AND is_active = TRUE"
                elif active is False:
                    base_sql += " AND is_active = FALSE"

                base_sql += " ORDER BY created_at DESC"

                # 执行查询
                rows = await conn.fetch(base_sql, user_id)
                return [dict(row) for row in rows]

            except Exception as e:
                logger.error(f"Error listing access keys for user {user_id}: {e}")
                raise

    async def get_access_key(self, key_id: str) -> Optional[dict]:
        """
        获取访问密钥信息

        Args:
            key_id: 密钥ID

        Returns:
            访问密钥字典，不存在则返回None
        """
        async with await self.get_connection() as conn:
            try:
                result = await conn.fetchrow(
                    "SELECT user_id, is_active FROM unifiles.access_keys WHERE id = $1",
                    key_id,
                )
                return dict(result) if result else None

            except Exception as e:
                logger.error(f"Error getting access key {key_id}: {e}")
                raise

    async def revoke_access_key(self, key_id: str) -> dict:
        """
        撤销（软删除）访问密钥

        Args:
            key_id: 密钥ID

        Returns:
            包含撤销结果的字典
        """
        async with await self.get_connection() as conn:
            try:
                # 调用数据库函数
                result = await conn.fetchval(
                    "SELECT unifiles.revoke_access_key($1)", key_id
                )

                # 解析 JSONB 结果
                if not isinstance(result, dict):
                    try:
                        result = json.loads(result)
                    except (json.JSONDecodeError, ValueError):
                        logger.error("Failed to parse revoke_access_key result")
                        return {
                            "success": False,
                            "error": "parse_error",
                            "message": "Failed to parse database response",
                        }

                return result

            except Exception as e:
                logger.error(f"Error revoking access key {key_id}: {e}")
                raise


# 全局实例
unified_user_db_manager = UserDBManager()
