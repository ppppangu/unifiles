"""
日志查询 API

提供：
1. 基础查询（按时间、层次、级别）
2. trace_id 关联查询
3. 业务字段查询（user_id, file_id, task_id）
4. 全文搜索
5. 统计分析
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from unifiles.core.database.pool_manager import get_pool_manager


router = APIRouter(prefix="/logs", tags=["logs"])


# ===== Response Models =====

class LogEntry(BaseModel):
    """日志条目"""
    id: int
    timestamp: datetime
    service_layer: str
    service_name: str
    level: str
    message: str
    context: dict
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    exception_type: Optional[str] = None
    module_name: Optional[str] = None
    function_name: Optional[str] = None


class LogQueryResponse(BaseModel):
    """日志查询响应"""
    success: bool
    total: int
    logs: List[LogEntry]
    query_time_ms: float


class LogStatsResponse(BaseModel):
    """日志统计响应"""
    success: bool
    stats: dict


# ===== API Endpoints =====

@router.get("/", response_model=LogQueryResponse)
async def query_logs(
    # 时间范围
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    last_hours: Optional[int] = Query(None, description="最近N小时", ge=1, le=168),

    # 过滤条件
    service_layer: Optional[str] = Query(None, description="服务层次", regex="^(app|worker|core)$"),
    service_name: Optional[str] = Query(None, description="服务名称"),
    level: Optional[str] = Query(None, description="日志级别"),

    # 业务字段
    user_id: Optional[str] = Query(None, description="用户ID"),
    file_id: Optional[str] = Query(None, description="文件ID"),
    task_id: Optional[str] = Query(None, description="任务ID"),

    # 全文搜索
    search: Optional[str] = Query(None, description="消息内容搜索"),

    # 分页
    limit: int = Query(100, description="返回数量", ge=1, le=1000),
    offset: int = Query(0, description="偏移量", ge=0),
):
    """
    查询日志

    示例：
    - 查询最近1小时的错误日志：
      GET /api/v1/logs?last_hours=1&level=ERROR

    - 查询特定用户的日志：
      GET /api/v1/logs?user_id=user_123&limit=50

    - 全文搜索：
      GET /api/v1/logs?search=connection failed
    """
    start = time.time()

    # 构建查询
    conditions = []
    params = []
    param_idx = 1

    # 时间范围
    if last_hours:
        start_time = datetime.now() - timedelta(hours=last_hours)

    if start_time:
        conditions.append(f"timestamp >= ${param_idx}")
        params.append(start_time)
        param_idx += 1

    if end_time:
        conditions.append(f"timestamp <= ${param_idx}")
        params.append(end_time)
        param_idx += 1

    # 过滤条件
    if service_layer:
        conditions.append(f"service_layer = ${param_idx}")
        params.append(service_layer)
        param_idx += 1

    if service_name:
        conditions.append(f"service_name = ${param_idx}")
        params.append(service_name)
        param_idx += 1

    if level:
        conditions.append(f"level = ${param_idx}")
        params.append(level)
        param_idx += 1

    # 业务字段（JSONB查询）
    if user_id:
        conditions.append(f"context @> ${param_idx}")
        params.append(json.dumps({"user_id": user_id}))
        param_idx += 1

    if file_id:
        conditions.append(f"context @> ${param_idx}")
        params.append(json.dumps({"file_id": file_id}))
        param_idx += 1

    if task_id:
        conditions.append(f"context @> ${param_idx}")
        params.append(json.dumps({"task_id": task_id}))
        param_idx += 1

    # 全文搜索
    if search:
        conditions.append(f"to_tsvector('english', message) @@ plainto_tsquery('english', ${param_idx})")
        params.append(search)
        param_idx += 1

    # 组装SQL
    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT
            id, timestamp, service_layer, service_name, level,
            message, context, trace_id, span_id,
            exception_type, module_name, function_name
        FROM unifiles.unified_logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    params.extend([limit, offset])

    # 执行查询
    pool_manager = await get_pool_manager()
    async with pool_manager.pg_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

        # 统计总数
        count_query = f"SELECT COUNT(*) FROM unifiles.unified_logs WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params[:-2])

    # 构建响应
    logs = [
        LogEntry(
            id=row['id'],
            timestamp=row['timestamp'],
            service_layer=row['service_layer'],
            service_name=row['service_name'],
            level=row['level'],
            message=row['message'],
            context=row['context'],
            trace_id=row['trace_id'],
            span_id=row['span_id'],
            exception_type=row['exception_type'],
            module_name=row['module_name'],
            function_name=row['function_name'],
        )
        for row in rows
    ]

    return LogQueryResponse(
        success=True,
        total=total,
        logs=logs,
        query_time_ms=(time.time() - start) * 1000
    )


@router.get("/trace/{trace_id}", response_model=LogQueryResponse)
async def query_by_trace_id(trace_id: str):
    """
    通过 trace_id 查询完整链路日志

    用途：从 Jaeger UI 跳转到日志详情
    """
    start = time.time()

    pool_manager = await get_pool_manager()
    async with pool_manager.pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM unifiles.get_logs_by_trace($1)",
            trace_id
        )

    if not rows:
        raise HTTPException(status_code=404, detail="No logs found for this trace_id")

    logs = [LogEntry(**dict(row)) for row in rows]

    return LogQueryResponse(
        success=True,
        total=len(logs),
        logs=logs,
        query_time_ms=(time.time() - start) * 1000
    )


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(
    since_hours: int = Query(24, description="统计最近N小时", ge=1, le=168)
):
    """
    获取日志统计信息

    返回：
    - 总日志数
    - 按级别统计
    - 按层次统计
    - 错误率
    - Top 10 错误类型
    - trace覆盖率
    """
    since_timestamp = datetime.now() - timedelta(hours=since_hours)

    pool_manager = await get_pool_manager()
    async with pool_manager.pg_pool.acquire() as conn:
        stats = await conn.fetchval(
            "SELECT unifiles.get_log_stats($1)",
            since_timestamp
        )

    return LogStatsResponse(
        success=True,
        stats=stats
    )


@router.get("/health", response_model=dict)
async def get_service_health():
    """
    获取服务健康状态（过去1小时）

    返回各服务的：
    - 总日志数
    - 错误数
    - 错误率
    - 最后活动时间
    """
    pool_manager = await get_pool_manager()
    async with pool_manager.pg_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM unifiles.service_health_1h")

    return {
        "success": True,
        "services": [dict(row) for row in rows]
    }
