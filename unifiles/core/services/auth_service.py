from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from fastapi import HTTPException, Request
from unifiles.core.logging import get_logger
logger = get_logger()

from unifiles.core.security.authorization import DatabaseSecurityEnforcer


class AuthService:
    """认证服务业务逻辑"""

    def __init__(self, pg_config: Dict[str, Any]):
        """
        初始化认证服务

        Args:
            pg_config: PostgreSQL配置
        """
        self.pg_config = pg_config
        self.security_enforcer = DatabaseSecurityEnforcer()
        self._connection_pool = None

    async def init_connection_pool(self, min_size: int = 5, max_size: int = 20):
        """
        初始化数据库连接池

        Args:
            min_size: 最小连接数
            max_size: 最大连接数
        """
        if not self._connection_pool:
            try:
                self._connection_pool = await asyncpg.create_pool(
                    **self.pg_config,
                    min_size=min_size,
                    max_size=max_size,
                    command_timeout=30,
                )
                logger.info("Auth service connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise

    async def validate_token(
        self, token: str, client_ip: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证访问令牌

        Args:
            token: 访问令牌
            client_ip: 客户端IP地址

        Returns:
            (是否有效, 用户信息)
        """
        if not token:
            return False, None

        try:
            # 确保连接池已初始化
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 查询令牌信息
                query = """
                    SELECT u.id, u.username, at.expires_at, at.is_active, at.last_used_at,
                           at.created_at, at.usage_count
                    FROM unifiles.access_tokens at
                    JOIN unifiles.users u ON at.user_id = u.id
                    WHERE at.token = $1 AND at.is_active = true
                """

                result = await conn.fetchrow(query, token)

                if not result:
                    logger.warning(f"Invalid token attempted from IP: {client_ip}")
                    return False, None

                # 检查令牌是否过期
                if result["expires_at"] and datetime.now() > result["expires_at"]:
                    logger.warning(
                        f"Expired token used by user {result['id']} from IP: {client_ip}"
                    )
                    await self._deactivate_token(conn, token)
                    return False, None

                # 更新令牌使用记录
                await self._update_token_usage(conn, token, client_ip)

                # 记录审计日志
                self.security_enforcer.audit_log(
                    operation="token_validation",
                    table="access_tokens",
                    user_id=result["id"],
                    details={
                        "client_ip": client_ip,
                        "last_used": datetime.now().isoformat(),
                    },
                )

                user_info = {
                    "user_id": result["id"],
                    "username": result["username"],
                    "token_created_at": result["created_at"].isoformat(),
                    "token_usage_count": result["usage_count"] + 1,
                }

                logger.debug(f"Token validated successfully for user: {result['id']}")
                return True, user_info

        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return False, None

    async def create_access_token(
        self,
        user_id: str,
        expires_in_hours: int = 24 * 7,  # 默认7天
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建访问令牌

        Args:
            user_id: 用户ID
            expires_in_hours: 过期时间（小时）
            description: 令牌描述

        Returns:
            令牌信息
        """
        try:
            import secrets

            # 生成安全的随机令牌
            token = secrets.token_urlsafe(32)
            expires_at = (
                datetime.now() + timedelta(hours=expires_in_hours)
                if expires_in_hours
                else None
            )

            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 插入新令牌
                query = """
                    INSERT INTO unifiles.access_tokens
                    (token, user_id, expires_at, description, is_active, created_at, usage_count)
                    VALUES ($1, $2, $3, $4, true, $5, 0)
                    RETURNING id
                """

                result = await conn.fetchrow(
                    query,
                    token,
                    user_id,
                    expires_at,
                    description or "API Access Token",
                    datetime.now(),
                )

                # 记录审计日志
                self.security_enforcer.audit_log(
                    operation="token_creation",
                    table="access_tokens",
                    user_id=user_id,
                    details={
                        "token_id": result["id"],
                        "expires_at": expires_at.isoformat() if expires_at else None,
                        "description": description,
                    },
                )

                logger.info(f"Access token created for user: {user_id}")

                return {
                    "token": token,
                    "token_id": result["id"],
                    "user_id": user_id,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "description": description or "API Access Token",
                    "created_at": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create access token: {e!s}"
            )

    async def revoke_token(self, token: str, user_id: Optional[str] = None) -> bool:
        """
        撤销访问令牌

        Args:
            token: 要撤销的令牌
            user_id: 用户ID（用于验证权限）

        Returns:
            是否撤销成功
        """
        try:
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 如果提供了user_id，验证令牌所有权
                if user_id:
                    verify_query = """
                        SELECT user_id FROM unifiles.access_tokens
                        WHERE token = $1 AND is_active = true
                    """
                    result = await conn.fetchrow(verify_query, token)

                    if not result or result["user_id"] != user_id:
                        logger.warning(
                            f"Unauthorized token revocation attempt by user: {user_id}"
                        )
                        return False

                # 撤销令牌
                await self._deactivate_token(conn, token)

                logger.info(f"Token revoked successfully by user: {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    async def get_user_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有令牌

        Args:
            user_id: 用户ID

        Returns:
            令牌列表
        """
        try:
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                query = """
                    SELECT id, description, created_at, expires_at, last_used_at,
                           usage_count, is_active
                    FROM unifiles.access_tokens
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """

                results = await conn.fetch(query, user_id)

                tokens = []
                for result in results:
                    tokens.append(
                        {
                            "token_id": result["id"],
                            "description": result["description"],
                            "created_at": result["created_at"].isoformat(),
                            "expires_at": result["expires_at"].isoformat()
                            if result["expires_at"]
                            else None,
                            "last_used_at": result["last_used_at"].isoformat()
                            if result["last_used_at"]
                            else None,
                            "usage_count": result["usage_count"],
                            "is_active": result["is_active"],
                        }
                    )

                return tokens

        except Exception as e:
            logger.error(f"Error getting user tokens: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get user tokens: {e!s}"
            )

    async def cleanup_expired_tokens(self) -> int:
        """
        清理过期的令牌

        Returns:
            清理的令牌数量
        """
        try:
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                query = """
                    UPDATE unifiles.access_tokens
                    SET is_active = false
                    WHERE expires_at < $1 AND is_active = true
                """

                result = await conn.execute(query, datetime.now())

                # 从result字符串中提取清理的数量
                cleaned_count = int(result.split()[-1]) if result else 0

                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired tokens")

                return cleaned_count

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            return 0

    async def _update_token_usage(
        self, conn: asyncpg.Connection, token: str, client_ip: Optional[str] = None
    ):
        """更新令牌使用记录"""
        try:
            update_query = """
                UPDATE unifiles.access_tokens
                SET last_used_at = $1, usage_count = usage_count + 1
                WHERE token = $2
            """
            await conn.execute(update_query, datetime.now(), token)

        except Exception as e:
            logger.warning(f"Failed to update token usage: {e}")

    async def _deactivate_token(self, conn: asyncpg.Connection, token: str):
        """停用令牌"""
        try:
            deactivate_query = """
                UPDATE unifiles.access_tokens
                SET is_active = false
                WHERE token = $1
            """
            await conn.execute(deactivate_query, token)

        except Exception as e:
            logger.error(f"Failed to deactivate token: {e}")
            raise

    async def extract_user_from_request(self, request: Request) -> Dict[str, Any]:
        """
        从请求中提取用户信息

        Args:
            request: FastAPI请求对象

        Returns:
            用户上下文信息
        """
        user_context = {
            "user_id": getattr(request.state, "user_id", None),
            "username": getattr(request.state, "username", None),
            "client_ip": getattr(request.state, "client_ip", None),
            "user_agent": request.headers.get("user-agent", ""),
            "request_id": getattr(request.state, "request_id", None),
            "token_info": getattr(request.state, "token_info", {}),
        }

        if not user_context["user_id"]:
            raise HTTPException(status_code=401, detail="Authentication required")

        return user_context

    async def close_connection_pool(self):
        """关闭连接池"""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
            logger.info("Auth service connection pool closed")
