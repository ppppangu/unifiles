"""
分布式追踪 - OpenTelemetry Tracing

功能：
- 自动 Instrumentation (FastAPI, asyncpg, httpx)
- 手动 Span 创建
- Trace 上下文传播
- OTLP Exporter

架构：
Application (Embedded SDK) → OTel Collector (Service) → Jaeger/Tempo
"""

import os
from typing import Any, Dict, Optional

from loguru import logger
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio


# 全局 Tracer 缓存
_tracer_cache: Dict[str, trace.Tracer] = {}


def init_opentelemetry(
    app: Any = None,
    service_name: str = "unifiles",
    service_version: str = "1.0.0",
    environment: str = "development",
    otlp_endpoint: Optional[str] = None,
    sampling_ratio: float = 1.0,
    enable_console_export: bool = False,
) -> trace.Tracer:
    """
    初始化 OpenTelemetry 追踪

    Args:
        app: FastAPI 应用实例（用于自动 Instrumentation）
        service_name: 服务名称
        service_version: 服务版本
        environment: 部署环境 (development, staging, production)
        otlp_endpoint: OTLP Collector 端点（默认 localhost:4317）
        sampling_ratio: 采样率 (0.0-1.0)，生产环境建议 0.1
        enable_console_export: 是否启用控制台导出（调试用）

    Returns:
        主 Tracer 实例

    环境变量配置:
        OTEL_ENABLED: 是否启用 OpenTelemetry (true/false)
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP Collector 端点
        OTEL_SAMPLING_RATIO: 采样率
    """
    # 检查是否启用
    otel_enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    if not otel_enabled:
        logger.info("OpenTelemetry is disabled (OTEL_ENABLED=false)")
        # 返回 NoOp Tracer
        return trace.get_tracer(service_name)

    logger.info(f"Initializing OpenTelemetry for service: {service_name}")

    # 1. 配置 Resource（服务标识）
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        DEPLOYMENT_ENVIRONMENT: environment,
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "opentelemetry",
    })

    # 2. 配置采样器（生产环境降低采样率）
    sampler = ParentBasedTraceIdRatio(
        ratio=float(os.getenv("OTEL_SAMPLING_RATIO", str(sampling_ratio)))
    )

    # 3. 创建 TracerProvider
    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    # 4. 配置 Exporter

    # OTLP Exporter (发送到 Collector)
    otlp_endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "localhost:4317"
    )

    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,  # 生产环境应该使用 TLS
        )

        provider.add_span_processor(
            BatchSpanProcessor(
                otlp_exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                schedule_delay_millis=5000,  # 5 秒批量发送
            )
        )

        logger.info(f"OTLP Exporter configured: {otlp_endpoint}")

    except Exception as e:
        logger.warning(f"Failed to configure OTLP Exporter: {e}")

    # Console Exporter (调试用)
    if enable_console_export or os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console Exporter enabled")

    # 5. 设置全局 TracerProvider
    trace.set_tracer_provider(provider)

    # 6. 自动 Instrumentation
    _setup_auto_instrumentation(app)

    # 7. 创建主 Tracer
    tracer = trace.get_tracer(service_name)

    logger.success(
        f"OpenTelemetry initialized: service={service_name}, "
        f"endpoint={otlp_endpoint}, sampling={sampling_ratio}"
    )

    return tracer


def _setup_auto_instrumentation(app: Any = None):
    """
    配置自动 Instrumentation

    自动追踪：
    - FastAPI: HTTP 请求/响应
    - asyncpg: PostgreSQL 查询
    - httpx: HTTP 客户端请求
    """
    try:
        # FastAPI Instrumentation
        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI auto-instrumentation enabled")

    except ImportError:
        logger.warning("FastAPI instrumentation not available (install opentelemetry-instrumentation-fastapi)")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")

    try:
        # asyncpg Instrumentation
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        logger.info("asyncpg auto-instrumentation enabled")

    except ImportError:
        logger.warning("asyncpg instrumentation not available (install opentelemetry-instrumentation-asyncpg)")
    except Exception as e:
        logger.error(f"Failed to instrument asyncpg: {e}")

    try:
        # httpx Instrumentation (用于 Webhook Worker)
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx auto-instrumentation enabled")

    except ImportError:
        logger.warning("httpx instrumentation not available (install opentelemetry-instrumentation-httpx)")
    except Exception as e:
        logger.error(f"Failed to instrument httpx: {e}")


def get_tracer(name: str) -> trace.Tracer:
    """
    获取命名的 Tracer（带缓存）

    Args:
        name: Tracer 名称（通常使用 __name__）

    Returns:
        Tracer 实例

    使用示例：
    ```python
    from unifiles.core.observability import get_tracer

    tracer = get_tracer(__name__)

    with tracer.start_as_current_span("my_operation"):
        # 业务逻辑
        pass
    ```
    """
    if name not in _tracer_cache:
        _tracer_cache[name] = trace.get_tracer(name)

    return _tracer_cache[name]


def get_current_span() -> trace.Span:
    """
    获取当前活动的 Span

    Returns:
        当前 Span（如果没有则返回 NoOp Span）

    使用示例：
    ```python
    from unifiles.core.observability import get_current_span

    span = get_current_span()
    span.set_attribute("user.id", "user_123")
    ```
    """
    return trace.get_current_span()


def add_span_attributes(attributes: Dict[str, Any]):
    """
    向当前 Span 添加属性

    Args:
        attributes: 属性字典

    使用示例：
    ```python
    from unifiles.core.observability import add_span_attributes

    add_span_attributes({
        "user.id": "user_123",
        "file.size": 1024000,
        "file.type": "pdf"
    })
    ```
    """
    span = get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    向当前 Span 添加事件

    Args:
        name: 事件名称
        attributes: 事件属性

    使用示例：
    ```python
    from unifiles.core.observability import add_span_event

    add_span_event(
        "file_validated",
        {"file.format": "pdf", "validation.result": "passed"}
    )
    ```
    """
    span = get_current_span()
    if span.is_recording():
        span.add_event(name, attributes or {})


def shutdown_tracing():
    """
    关闭 Tracing（应用退出时调用）

    确保所有 Span 都已导出
    """
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, 'shutdown'):
            provider.shutdown()
            logger.info("OpenTelemetry TracerProvider shutdown completed")
    except Exception as e:
        logger.error(f"Error during TracerProvider shutdown: {e}")
