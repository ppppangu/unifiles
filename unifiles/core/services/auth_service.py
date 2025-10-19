from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from fastapi import HTTPException, Request
from loguru import logger

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
        验证访问密钥（使用数据库的validate_access_key函数）

        Args:
            token: 访问密钥
            client_ip: 客户端IP地址

        Returns:
            (是否有效, 用户信息和权限)
        """
        if not token:
            return False, None

        try:
            # 确保连接池已初始化
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 调用数据库的validate_access_key函数
                import json
                validation_result = await conn.fetchval(
                    "SELECT validate_access_key($1, $2)",
                    token,
                    client_ip
                )

                result_dict = json.loads(validation_result)

                if not result_dict.get("valid"):
                    error = result_dict.get("error", "invalid_token")
                    logger.warning(
                        f"Invalid token attempted from IP: {client_ip}, error: {error}"
                    )
                    return False, None

                # 获取用户名
                user_id = result_dict.get("user_id")
                username_query = "SELECT username FROM unifiles.users WHERE id = $1"
                username = await conn.fetchval(username_query, user_id)

                # 记录审计日志
                self.security_enforcer.audit_log(
                    operation="token_validation",
                    table="access_keys",
                    user_id=user_id,
                    details={
                        "client_ip": client_ip,
                        "last_used": datetime.now().isoformat(),
                    },
                )

                user_info = {
                    "user_id": user_id,
                    "username": username,
                    "scopes": result_dict.get("scopes", []),
                    "permissions": {
                        "can_create_kb": result_dict.get("can_create_kb"),
                        "can_delete_files": result_dict.get("can_delete_files"),
                        "can_share_files": result_dict.get("can_share_files"),
                        "can_export_data": result_dict.get("can_export_data"),
                        "max_file_size_mb": result_dict.get("max_file_size_mb"),
                        "max_knowledge_bases": result_dict.get("max_knowledge_bases"),
                    }
                }

                logger.debug(f"Token validated successfully for user: {user_id}")
                return True, user_info

        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return False, None

    async def create_access_token(
        self,
        user_id: str,
        name: str = "API Access Key",
        description: Optional[str] = None,
        expires_in_hours: Optional[int] = None,
        scopes: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建访问密钥（使用数据库的create_access_key函数）

        Args:
            user_id: 用户ID
            name: 密钥名称
            description: 密钥描述
            expires_in_hours: 过期时间（小时），None表示永不过期
            scopes: 权限范围
            **kwargs: 其他配置参数（max_requests_per_hour, max_requests_per_day等）

        Returns:
            密钥信息
        """
        try:
            import json

            expires_at = (
                datetime.now() + timedelta(hours=expires_in_hours)
                if expires_in_hours
                else None
            )

            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 调用数据库的create_access_key函数
                result = await conn.fetchval(
                    """
                    SELECT create_access_key(
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                    )
                    """,
                    user_id,
                    name,
                    description,
                    scopes or ["read", "write"],
                    expires_at,
                    kwargs.get("max_requests_per_hour", 1000),
                    kwargs.get("max_requests_per_day", 10000),
                    kwargs.get("max_file_size_mb", 100),
                    kwargs.get("max_knowledge_bases", 10),
                    kwargs.get("can_create_kb", True),
                    kwargs.get("can_delete_files", True),
                    kwargs.get("can_share_files", True),
                    kwargs.get("can_export_data", True),
                    kwargs.get("allowed_ips")
                )

                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    error_msg = result_dict.get("message", "Failed to create access key")
                    logger.error(f"Error creating access key: {error_msg}")
                    raise HTTPException(status_code=500, detail=error_msg)

                # 记录审计日志
                self.security_enforcer.audit_log(
                    operation="token_creation",
                    table="access_keys",
                    user_id=user_id,
                    details={
                        "key_id": result_dict.get("key_id"),
                        "name": name,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                    },
                )

                logger.info(f"Access key created for user: {user_id}")

                return {
                    "access_key": result_dict.get("access_key"),
                    "key_id": result_dict.get("key_id"),
                    "user_id": user_id,
                    "name": name,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "description": description,
                    "created_at": datetime.now().isoformat(),
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create access token: {e!s}"
            )

    async def revoke_token(self, key_id: str, user_id: Optional[str] = None) -> bool:
        """
        撤销访问密钥

        Args:
            key_id: 要撤销的密钥ID
            user_id: 用户ID（用于验证权限）

        Returns:
            是否撤销成功
        """
        try:
            import json

            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 如果提供了user_id，验证密钥所有权
                if user_id:
                    verify_query = """
                        SELECT user_id FROM unifiles.access_keys
                        WHERE id = $1 AND is_active = true
                    """
                    result = await conn.fetchrow(verify_query, key_id)

                    if not result or result["user_id"] != user_id:
                        logger.warning(
                            f"Unauthorized key revocation attempt by user: {user_id}"
                        )
                        return False

                # 调用数据库的revoke_access_key函数
                revoke_result = await conn.fetchval(
                    "SELECT revoke_access_key($1)",
                    key_id
                )

                result_dict = json.loads(revoke_result)

                if result_dict.get("success"):
                    logger.info(f"Access key {key_id} revoked successfully by user: {user_id}")
                    return True
                else:
                    logger.warning(f"Failed to revoke key: {result_dict.get('message')}")
                    return False

        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    async def get_user_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有访问密钥

        Args:
            user_id: 用户ID

        Returns:
            密钥列表
        """
        try:
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 使用access_keys_overview视图，它隐藏了敏感的access_key字段
                query = """
                    SELECT id, name, description, scopes, is_active,
                           total_requests, requests_today, requests_this_hour,
                           max_requests_per_hour, max_requests_per_day,
                           created_at, expires_at, last_used_at,
                           expiry_status, hourly_usage_percent, daily_usage_percent
                    FROM unifiles.access_keys_overview
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """

                results = await conn.fetch(query, user_id)

                keys = []
                for result in results:
                    keys.append(
                        {
                            "key_id": result["id"],
                            "name": result["name"],
                            "description": result["description"],
                            "scopes": result["scopes"],
                            "is_active": result["is_active"],
                            "total_requests": result["total_requests"],
                            "requests_today": result["requests_today"],
                            "requests_this_hour": result["requests_this_hour"],
                            "max_requests_per_hour": result["max_requests_per_hour"],
                            "max_requests_per_day": result["max_requests_per_day"],
                            "created_at": result["created_at"].isoformat(),
                            "expires_at": result["expires_at"].isoformat()
                            if result["expires_at"]
                            else None,
                            "last_used_at": result["last_used_at"].isoformat()
                            if result["last_used_at"]
                            else None,
                            "expiry_status": result["expiry_status"],
                            "hourly_usage_percent": float(result["hourly_usage_percent"]) if result["hourly_usage_percent"] else None,
                            "daily_usage_percent": float(result["daily_usage_percent"]) if result["daily_usage_percent"] else None,
                        }
                    )

                return keys

        except Exception as e:
            logger.error(f"Error getting user tokens: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get user tokens: {e!s}"
            )

    async def cleanup_expired_tokens(self) -> int:
        """
        清理过期的访问密钥（使用数据库的cleanup_expired_access_keys函数）

        Returns:
            清理的密钥数量
        """
        try:
            if not self._connection_pool:
                await self.init_connection_pool()

            async with self._connection_pool.acquire() as conn:
                # 调用数据库的cleanup_expired_access_keys函数
                cleaned_count = await conn.fetchval(
                    "SELECT cleanup_expired_access_keys()"
                )

                if cleaned_count and cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired access keys")

                return cleaned_count or 0

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            return 0

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
            "scopes": getattr(request.state, "scopes", []),
            "permissions": getattr(request.state, "permissions", {}),
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
