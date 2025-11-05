"""
可观测性模块 - OpenTelemetry 集成

提供：
- 分布式追踪 (Traces)
- 指标监控 (Metrics)
- 结构化日志 (Logs)

使用示例：
```python
from unifiles.core.observability import init_opentelemetry, get_tracer

# 初始化（在应用启动时）
app = FastAPI()
init_opentelemetry(app, service_name="unifiles-api")

# 使用 Tracer
tracer = get_tracer(__name__)

with tracer.start_as_current_span("my_operation"):
    # 业务逻辑
    pass
```
"""

from unifiles.core.observability.tracing import (
    init_opentelemetry,
    get_tracer,
    get_current_span,
    add_span_attributes,
    add_span_event,
)

from unifiles.core.observability.metrics import (
    init_metrics,
    get_metrics_registry,
)

__all__ = [
    # Tracing
    "init_opentelemetry",
    "get_tracer",
    "get_current_span",
    "add_span_attributes",
    "add_span_event",

    # Metrics
    "init_metrics",
    "get_metrics_registry",
]
