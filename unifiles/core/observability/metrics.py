"""
指标监控 - Prometheus Metrics

功能：
- Counter: 累计计数（如总请求数）
- Gauge: 瞬时值（如当前队列长度）
- Histogram: 分布统计（如请求耗时）
- Summary: 摘要统计（如 P95 延迟）

用途：
- Redis 操作统计（高频操作用 Metrics 不用 Traces）
- 队列长度监控
- 业务指标（上传文件数、处理任务数等）
"""

import time
from typing import Any, Dict, Optional

from loguru import logger
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


# 全局 Metrics Registry
_metrics_registry: Optional[CollectorRegistry] = None

# 预定义的 Metrics
_metrics_cache: Dict[str, Any] = {}


def init_metrics() -> CollectorRegistry:
    """
    初始化 Prometheus Metrics

    Returns:
        CollectorRegistry 实例

    使用示例：
    ```python
    from unifiles.core.observability import init_metrics

    registry = init_metrics()
    ```
    """
    global _metrics_registry

    if _metrics_registry is not None:
        logger.warning("Metrics already initialized, returning existing registry")
        return _metrics_registry

    logger.info("Initializing Prometheus Metrics")

    # 创建独立的 Registry（避免与其他库冲突）
    _metrics_registry = CollectorRegistry()

    # 注册核心 Metrics
    _register_core_metrics()

    logger.success("Prometheus Metrics initialized")

    return _metrics_registry


def get_metrics_registry() -> CollectorRegistry:
    """
    获取 Metrics Registry

    Returns:
        CollectorRegistry 实例（如果未初始化则自动初始化）
    """
    global _metrics_registry

    if _metrics_registry is None:
        _metrics_registry = init_metrics()

    return _metrics_registry


def _register_core_metrics():
    """注册核心业务 Metrics"""
    global _metrics_cache, _metrics_registry

    # ===== 文件操作 Metrics =====

    _metrics_cache['file_uploads_total'] = Counter(
        'unifiles_file_uploads_total',
        'Total file uploads',
        ['user_id', 'status'],  # status: success, failed
        registry=_metrics_registry
    )

    _metrics_cache['file_upload_bytes_total'] = Counter(
        'unifiles_file_upload_bytes_total',
        'Total bytes uploaded',
        ['storage_backend'],
        registry=_metrics_registry
    )

    _metrics_cache['file_upload_duration_seconds'] = Histogram(
        'unifiles_file_upload_duration_seconds',
        'File upload duration in seconds',
        ['storage_backend'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        registry=_metrics_registry
    )

    # ===== Redis 操作 Metrics =====

    _metrics_cache['redis_operations_total'] = Counter(
        'unifiles_redis_operations_total',
        'Total Redis operations',
        ['operation', 'status'],  # operation: enqueue, dequeue, publish, etc.
        registry=_metrics_registry
    )

    _metrics_cache['redis_operation_duration_seconds'] = Histogram(
        'unifiles_redis_operation_duration_seconds',
        'Redis operation duration in seconds',
        ['operation'],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        registry=_metrics_registry
    )

    # ===== 队列 Metrics =====

    _metrics_cache['queue_length'] = Gauge(
        'unifiles_queue_length',
        'Current queue length',
        ['queue_name'],
        registry=_metrics_registry
    )

    _metrics_cache['queue_tasks_processed_total'] = Counter(
        'unifiles_queue_tasks_processed_total',
        'Total tasks processed',
        ['queue_name', 'status'],  # status: completed, failed
        registry=_metrics_registry
    )

    _metrics_cache['queue_task_duration_seconds'] = Histogram(
        'unifiles_queue_task_duration_seconds',
        'Task processing duration in seconds',
        ['queue_name', 'task_type'],
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
        registry=_metrics_registry
    )

    # ===== Worker Metrics =====

    _metrics_cache['worker_tasks_current'] = Gauge(
        'unifiles_worker_tasks_current',
        'Current tasks being processed',
        ['worker_name'],
        registry=_metrics_registry
    )

    _metrics_cache['worker_tasks_total'] = Counter(
        'unifiles_worker_tasks_total',
        'Total tasks processed by worker',
        ['worker_name', 'status'],
        registry=_metrics_registry
    )

    # ===== 存储 Metrics =====

    _metrics_cache['storage_operations_total'] = Counter(
        'unifiles_storage_operations_total',
        'Total storage operations',
        ['backend', 'operation', 'status'],  # operation: upload, download, delete
        registry=_metrics_registry
    )

    _metrics_cache['storage_operation_duration_seconds'] = Histogram(
        'unifiles_storage_operation_duration_seconds',
        'Storage operation duration in seconds',
        ['backend', 'operation'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        registry=_metrics_registry
    )

    # ===== 数据库 Metrics =====

    _metrics_cache['db_queries_total'] = Counter(
        'unifiles_db_queries_total',
        'Total database queries',
        ['operation', 'table'],  # operation: SELECT, INSERT, UPDATE, DELETE
        registry=_metrics_registry
    )

    _metrics_cache['db_query_duration_seconds'] = Histogram(
        'unifiles_db_query_duration_seconds',
        'Database query duration in seconds',
        ['operation'],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        registry=_metrics_registry
    )

    logger.info("Core metrics registered")


# ===== 便捷函数 =====

def get_metric(name: str) -> Any:
    """
    获取已注册的 Metric

    Args:
        name: Metric 名称

    Returns:
        Metric 实例

    使用示例：
    ```python
    from unifiles.core.observability.metrics import get_metric

    counter = get_metric('file_uploads_total')
    counter.labels(user_id='user_123', status='success').inc()
    ```
    """
    if name not in _metrics_cache:
        raise ValueError(f"Metric '{name}' not found. Available: {list(_metrics_cache.keys())}")

    return _metrics_cache[name]


def track_file_upload(
    user_id: str,
    storage_backend: str,
    file_size: int,
    duration_seconds: float,
    status: str = "success"
):
    """
    记录文件上传 Metrics

    Args:
        user_id: 用户 ID
        storage_backend: 存储后端
        file_size: 文件大小（字节）
        duration_seconds: 上传耗时（秒）
        status: 状态（success, failed）

    使用示例：
    ```python
    from unifiles.core.observability.metrics import track_file_upload

    track_file_upload(
        user_id="user_123",
        storage_backend="minio",
        file_size=1024000,
        duration_seconds=2.5,
        status="success"
    )
    ```
    """
    get_metric('file_uploads_total').labels(
        user_id=user_id,
        status=status
    ).inc()

    get_metric('file_upload_bytes_total').labels(
        storage_backend=storage_backend
    ).inc(file_size)

    get_metric('file_upload_duration_seconds').labels(
        storage_backend=storage_backend
    ).observe(duration_seconds)


def track_redis_operation(
    operation: str,
    duration_seconds: float,
    status: str = "success"
):
    """
    记录 Redis 操作 Metrics

    Args:
        operation: 操作类型（enqueue, dequeue, publish, etc.）
        duration_seconds: 操作耗时（秒）
        status: 状态（success, failed）

    使用示例：
    ```python
    from unifiles.core.observability.metrics import track_redis_operation

    start_time = time.time()
    await redis.lpush("queue:upload", task_json)
    track_redis_operation(
        operation="enqueue",
        duration_seconds=time.time() - start_time,
        status="success"
    )
    ```
    """
    get_metric('redis_operations_total').labels(
        operation=operation,
        status=status
    ).inc()

    get_metric('redis_operation_duration_seconds').labels(
        operation=operation
    ).observe(duration_seconds)


def set_queue_length(queue_name: str, length: int):
    """
    设置队列长度 Gauge

    Args:
        queue_name: 队列名称
        length: 当前长度

    使用示例：
    ```python
    from unifiles.core.observability.metrics import set_queue_length

    length = await redis.llen("unifiles:queue:file_upload")
    set_queue_length("file_upload", length)
    ```
    """
    get_metric('queue_length').labels(
        queue_name=queue_name
    ).set(length)


def track_task_processing(
    queue_name: str,
    task_type: str,
    duration_seconds: float,
    status: str = "completed"
):
    """
    记录任务处理 Metrics

    Args:
        queue_name: 队列名称
        task_type: 任务类型
        duration_seconds: 处理耗时（秒）
        status: 状态（completed, failed）

    使用示例：
    ```python
    from unifiles.core.observability.metrics import track_task_processing

    start_time = time.time()
    await process_task(task)
    track_task_processing(
        queue_name="file_upload",
        task_type="file_upload",
        duration_seconds=time.time() - start_time,
        status="completed"
    )
    ```
    """
    get_metric('queue_tasks_processed_total').labels(
        queue_name=queue_name,
        status=status
    ).inc()

    get_metric('queue_task_duration_seconds').labels(
        queue_name=queue_name,
        task_type=task_type
    ).observe(duration_seconds)


def generate_metrics() -> bytes:
    """
    生成 Prometheus 格式的 Metrics

    Returns:
        Prometheus 文本格式的 Metrics

    使用示例（FastAPI）：
    ```python
    from fastapi import Response
    from unifiles.core.observability.metrics import generate_metrics, CONTENT_TYPE_LATEST

    @app.get("/metrics")
    async def metrics():
        return Response(
            content=generate_metrics(),
            media_type=CONTENT_TYPE_LATEST
        )
    ```
    """
    registry = get_metrics_registry()
    return generate_latest(registry)
