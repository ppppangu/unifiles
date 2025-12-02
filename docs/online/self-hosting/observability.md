# 可观测性

本文档介绍如何配置 Unifiles 的日志、指标和追踪，实现全面的可观测性。

## 可观测性三大支柱

```
┌─────────────────────────────────────────────────────────────┐
│                      可观测性平台                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│     日志        │      指标       │         追踪            │
│    (Logs)       │   (Metrics)     │       (Traces)          │
├─────────────────┼─────────────────┼─────────────────────────┤
│    Loki         │   Prometheus    │        Jaeger           │
│  Elasticsearch  │    VictoriaM    │        Zipkin           │
│                 │                 │     OpenTelemetry       │
└─────────────────┴─────────────────┴─────────────────────────┘
```

## 日志配置

### 应用日志

Unifiles 使用 loguru 进行日志记录:

```python
# 日志配置
from loguru import logger
import sys

# 配置日志格式
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            "level": "INFO"
        },
        {
            "sink": "/var/log/unifiles/app.log",
            "rotation": "100 MB",
            "retention": "30 days",
            "compression": "gz",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            "level": "DEBUG"
        }
    ]
)
```

### 日志级别

通过环境变量配置:

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 结构化日志

```python
# 使用结构化上下文
logger.bind(
    request_id="req_123",
    user_id="user_456"
).info("Processing file upload")

# 输出
# 2024-01-15 10:30:00 | INFO | ... | request_id=req_123 user_id=user_456 Processing file upload
```

### 日志收集 (Loki + Promtail)

```yaml
# docker-compose-logging.yml
version: '3.8'

services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log/unifiles:/var/log/unifiles:ro
      - ./promtail-config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml

volumes:
  loki_data:
```

Promtail 配置:

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: unifiles
    static_configs:
      - targets:
          - localhost
        labels:
          job: unifiles
          __path__: /var/log/unifiles/*.log
    pipeline_stages:
      - regex:
          expression: '^(?P<timestamp>\S+ \S+) \| (?P<level>\w+) \| (?P<location>[^|]+) \| (?P<message>.*)$'
      - labels:
          level:
      - timestamp:
          source: timestamp
          format: "2006-01-02 15:04:05"
```

## 指标配置

### 内置指标

Unifiles 暴露 Prometheus 格式的指标:

```bash
# 启用指标
METRICS_ENABLED=true
METRICS_PORT=9090
```

### 可用指标

| 指标名称 | 类型 | 描述 |
|---------|------|------|
| `unifiles_requests_total` | Counter | 总请求数 |
| `unifiles_request_duration_seconds` | Histogram | 请求延迟 |
| `unifiles_files_uploaded_total` | Counter | 上传文件数 |
| `unifiles_files_processed_total` | Counter | 处理文件数 |
| `unifiles_extraction_duration_seconds` | Histogram | 提取耗时 |
| `unifiles_search_duration_seconds` | Histogram | 搜索耗时 |
| `unifiles_queue_size` | Gauge | 队列大小 |
| `unifiles_active_workers` | Gauge | 活跃 Worker 数 |

### Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Unifiles API
  - job_name: 'unifiles-api'
    static_configs:
      - targets: ['api:9090']
    
  # Unifiles Workers
  - job_name: 'unifiles-workers'
    static_configs:
      - targets: ['worker-upload:9090', 'worker-extraction:9090']
  
  # PostgreSQL (需要 postgres_exporter)
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  # Redis (需要 redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  # MinIO
  - job_name: 'minio'
    metrics_path: /minio/v2/metrics/cluster
    static_configs:
      - targets: ['minio:9000']
```

### Docker Compose 监控栈

```yaml
# docker-compose-monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://unifiles:password@postgres:5432/unifiles?sslmode=disable"

  redis-exporter:
    image: oliver006/redis_exporter:latest
    environment:
      REDIS_ADDR: "redis:6379"
      REDIS_PASSWORD: "your_redis_password"

volumes:
  prometheus_data:
  grafana_data:
```

### 告警规则

```yaml
# alert-rules.yml
groups:
  - name: unifiles
    rules:
      # 高错误率
      - alert: HighErrorRate
        expr: |
          sum(rate(unifiles_requests_total{status=~"5.."}[5m])) 
          / sum(rate(unifiles_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      # 高延迟
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, 
            sum(rate(unifiles_request_duration_seconds_bucket[5m])) by (le)
          ) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s"

      # 队列积压
      - alert: QueueBacklog
        expr: unifiles_queue_size > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Queue backlog detected"
          description: "Queue size is {{ $value }}"

      # 数据库连接
      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 150
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connections high"
```

## 追踪配置

### OpenTelemetry 集成

```bash
# 启用追踪
OTEL_ENABLED=true
OTEL_SERVICE_NAME=unifiles
OTEL_EXPORTER_ENDPOINT=otel-collector:4317
```

### 应用代码追踪

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# 配置追踪
provider = TracerProvider()
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="otel-collector:4317")
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# 使用追踪
@tracer.start_as_current_span("process_file")
async def process_file(file_id: str):
    span = trace.get_current_span()
    span.set_attribute("file.id", file_id)
    
    with tracer.start_as_current_span("extract_content"):
        content = await extract(file_id)
    
    with tracer.start_as_current_span("generate_embeddings"):
        embeddings = await embed(content)
    
    return embeddings
```

### OpenTelemetry Collector

```yaml
# otel-collector-config.yml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

### Jaeger UI

```yaml
# docker-compose-tracing.yml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"
      - "4318:4318"
      - "8889:8889"
    volumes:
      - ./otel-collector-config.yml:/etc/otel/config.yaml
    command: ["--config=/etc/otel/config.yaml"]

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "14250:14250"
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

## Grafana 仪表板

### 概览仪表板

```json
{
  "dashboard": {
    "title": "Unifiles Overview",
    "panels": [
      {
        "title": "Requests per Second",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(unifiles_requests_total[5m]))",
            "legendFormat": "RPS"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(unifiles_requests_total{status=~\"5..\"}[5m])) / sum(rate(unifiles_requests_total[5m])) * 100",
            "legendFormat": "Error %"
          }
        ]
      },
      {
        "title": "P95 Latency",
        "type": "gauge",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(unifiles_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "P95"
          }
        ]
      },
      {
        "title": "Queue Size",
        "type": "graph",
        "targets": [
          {
            "expr": "unifiles_queue_size",
            "legendFormat": "{{ queue }}"
          }
        ]
      }
    ]
  }
}
```

### 数据源配置

```yaml
# grafana/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
```

## 健康检查端点

### 内置健康检查

```bash
# 基础健康检查
GET /health
# Response: {"status": "healthy", "version": "1.0.0"}

# 详细健康检查
GET /health/detailed
# Response:
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy", "latency_ms": 5},
    "redis": {"status": "healthy", "latency_ms": 1},
    "storage": {"status": "healthy", "latency_ms": 10}
  },
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

### Kubernetes 探针配置

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8088
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/detailed
    port: 8088
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

## 下一步

- [备份与恢复](./backup-restore.md) - 数据保护策略
- [故障排除](./troubleshooting.md) - 使用可观测性排查问题
- [升级指南](./upgrade.md) - 监控升级过程
