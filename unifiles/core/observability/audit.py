"""
审计日志 - 混合架构（Database + OpenTelemetry）

功能：
- 数据库审计日志（持久化、事务性、合规性）
- OpenTelemetry 事件关联（通过 trace_id 关联）
- 业务事件记录

设计原则：
- 数据库日志: 完整、持久、事务性（7 年保留）
- OTel 事件: 实时监控、性能分析（30 天保留）
- 通过 trace_id 关联两者
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

import asyncpg
from loguru import logger
from opentelemetry import trace


class AuditLogger:
    """
    混合审计日志记录器

    职责：
    1. 记录业务事件到数据库（合规性）
    2. 关联 OpenTelemetry Trace ID（可观测性）
    3. 添加 Span 事件（实时监控）

    使用示例：
    ```python
    audit_logger = AuditLogger(db_pool)

    # 在事务中记录审计日志
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("INSERT INTO files ...")

            await audit_logger.log_activity(
                user_id="user_123",
                activity_type="file_upload",
                details={"file_id": "file_456"},
                ip_address="192.168.1.100",
                user_agent="Chrome/120.0",
                conn=conn  # 使用同一事务
            )
    ```
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        初始化审计日志记录器

        Args:
            db_pool: 数据库连接池
        """
        self.db_pool = db_pool

    async def log_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        conn: Optional[asyncpg.Connection] = None
    ) -> str:
        """
        记录用户活动（数据库 + OTel）

        Args:
            user_id: 用户 ID
            activity_type: 活动类型 (file_upload, file_delete, etc.)
            details: 活动详情
            ip_address: 客户端 IP
            user_agent: 用户代理
            conn: 数据库连接（用于事务，可选）

        Returns:
            审计日志 ID

        业务事件类型:
        - file_upload: 文件上传
        - file_download: 文件下载
        - file_delete: 文件删除
        - file_share: 文件分享
        - user_login: 用户登录
        - user_logout: 用户登出
        - api_key_created: API Key 创建
        - payment: 支付
        """
        # 1. 获取当前 Trace 上下文
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        trace_id = None
        span_id = None

        if span_context.is_valid:
            # 格式化为 32 位十六进制字符串（标准格式）
            trace_id = format(span_context.trace_id, '032x')
            span_id = format(span_context.span_id, '016x')

        # 2. 写入数据库（事务性、持久化）
        db = conn or self.db_pool

        log_id = await db.fetchval("""
            INSERT INTO unifiles.user_activity_logs
            (user_id, activity_type, activity_details, ip_address, user_agent, trace_id, span_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, user_id, activity_type, json.dumps(details), ip_address, user_agent, trace_id, span_id)

        # 3. 添加 OTel 事件（用于实时监控）
        if current_span.is_recording():
            current_span.add_event(
                name=f"audit.{activity_type}",
                attributes={
                    "audit.log_id": log_id,
                    "audit.user_id": user_id,
                    "audit.activity_type": activity_type,
                    "audit.details": json.dumps(details),
                    "audit.ip_address": ip_address or "unknown",
                }
            )

        logger.debug(
            f"Audit log recorded: {activity_type} by {user_id} "
            f"(log_id={log_id}, trace_id={trace_id})"
        )

        return log_id

    async def log_file_operation(
        self,
        user_id: str,
        operation: str,
        file_id: str,
        filename: str,
        file_size: Optional[int] = None,
        storage_backend: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        conn: Optional[asyncpg.Connection] = None
    ) -> str:
        """
        记录文件操作（便捷方法）

        Args:
            user_id: 用户 ID
            operation: 操作类型 (upload, download, delete)
            file_id: 文件 ID
            filename: 文件名
            file_size: 文件大小（字节）
            storage_backend: 存储后端
            ip_address: 客户端 IP
            user_agent: 用户代理
            conn: 数据库连接（用于事务）

        Returns:
            审计日志 ID
        """
        details = {
            "file_id": file_id,
            "filename": filename,
        }

        if file_size is not None:
            details["file_size"] = file_size

        if storage_backend is not None:
            details["storage_backend"] = storage_backend

        return await self.log_activity(
            user_id=user_id,
            activity_type=f"file_{operation}",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            conn=conn
        )

    async def log_authentication(
        self,
        user_id: str,
        event: str,
        ip_address: str,
        user_agent: str,
        success: bool = True,
        failure_reason: Optional[str] = None,
        conn: Optional[asyncpg.Connection] = None
    ) -> str:
        """
        记录认证事件（便捷方法）

        Args:
            user_id: 用户 ID
            event: 事件类型 (login, logout, token_refresh)
            ip_address: 客户端 IP
            user_agent: 用户代理
            success: 是否成功
            failure_reason: 失败原因（如果失败）
            conn: 数据库连接

        Returns:
            审计日志 ID
        """
        details = {
            "event": event,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if not success and failure_reason:
            details["failure_reason"] = failure_reason

        return await self.log_activity(
            user_id=user_id,
            activity_type=f"user_{event}",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            conn=conn
        )

    async def get_user_activities(
        self,
        user_id: str,
        activity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Dict[str, Any]]:
        """
        查询用户活动历史

        Args:
            user_id: 用户 ID
            activity_type: 活动类型过滤（可选）
            limit: 返回数量
            offset: 偏移量

        Returns:
            活动记录列表
        """
        if activity_type:
            rows = await self.db_pool.fetch("""
                SELECT
                    id,
                    user_id,
                    activity_type,
                    activity_details,
                    ip_address,
                    user_agent,
                    trace_id,
                    span_id,
                    created_at
                FROM unifiles.user_activity_logs
                WHERE user_id = $1 AND activity_type = $2
                ORDER BY created_at DESC
                LIMIT $3 OFFSET $4
            """, user_id, activity_type, limit, offset)
        else:
            rows = await self.db_pool.fetch("""
                SELECT
                    id,
                    user_id,
                    activity_type,
                    activity_details,
                    ip_address,
                    user_agent,
                    trace_id,
                    span_id,
                    created_at
                FROM unifiles.user_activity_logs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """, user_id, limit, offset)

        return [dict(row) for row in rows]

    async def get_activity_by_trace_id(
        self,
        trace_id: str
    ) -> list[Dict[str, Any]]:
        """
        通过 Trace ID 查询关联的审计日志

        用途：从 Jaeger UI 跳转到审计详情

        Args:
            trace_id: OpenTelemetry Trace ID (32 位十六进制)

        Returns:
            关联的审计日志列表
        """
        rows = await self.db_pool.fetch("""
            SELECT
                id,
                user_id,
                activity_type,
                activity_details,
                ip_address,
                user_agent,
                trace_id,
                span_id,
                created_at
            FROM unifiles.user_activity_logs
            WHERE trace_id = $1
            ORDER BY created_at DESC
        """, trace_id)

        return [dict(row) for row in rows]


# ===== 全局实例（可选） =====

_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_pool: Optional[asyncpg.Pool] = None) -> AuditLogger:
    """
    获取全局审计日志记录器（单例）

    Args:
        db_pool: 数据库连接池（首次调用时必须提供）

    Returns:
        AuditLogger 实例
    """
    global _global_audit_logger

    if _global_audit_logger is None:
        if db_pool is None:
            raise ValueError("db_pool is required for first-time initialization")

        _global_audit_logger = AuditLogger(db_pool)
        logger.info("Global AuditLogger initialized")

    return _global_audit_logger
