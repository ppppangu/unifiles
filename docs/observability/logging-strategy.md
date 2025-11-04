# 日志策略深度分析：OpenTelemetry vs PostgreSQL 日志

**文档版本**: 1.0
**创建日期**: 2025-01-16
**分析对象**: 日志架构选型（OpenTelemetry vs Database Audit Logs）

---

## 📋 目录

1. [核心问题](#核心问题)
2. [OpenTelemetry 深度解析](#opentelemetry-深度解析)
3. [数据库审计日志深度解析](#数据库审计日志深度解析)
4. [两者关系与差异](#两者关系与差异)
5. [替换方案利弊分析](#替换方案利弊分析)
6. [推荐架构方案](#推荐架构方案)
7. [实施指南](#实施指南)
8. [总结和建议](#总结和建议)

---

## 核心问题

### 用户的疑问

> 用 OpenTelemetry 替换把日志记录在 PostgreSQL 中有什么利弊？日志模块详细分析。这是个服务化的东西吗，还是嵌入式的？

### 关键概念辨析

**首先需要明确**: OpenTelemetry 和 PostgreSQL 审计日志 **不是替代关系，而是互补关系**。

```
错误理解:
OpenTelemetry ❌ 替换 ❌ PostgreSQL 审计日志

正确理解:
OpenTelemetry (可观测性) + PostgreSQL 审计日志 (合规性) = 完整解决方案
```

---

## OpenTelemetry 深度解析

### 什么是 OpenTelemetry？

**OpenTelemetry (OTel)** 是一个 **可观测性框架**，提供三大支柱（Three Pillars of Observability）：

```
┌─────────────────────────────────────────────────┐
│          OpenTelemetry (可观测性)               │
├─────────────────┬─────────────────┬─────────────┤
│   Traces        │    Metrics      │    Logs     │
│  (分布式追踪)    │   (指标监控)    │  (结构化日志)│
└─────────────────┴─────────────────┴─────────────┘
```

#### 1. Traces (分布式追踪)

**目的**: 追踪单个请求的完整生命周期

```python
# 示例：追踪文件上传请求
Request ID: req_abc123

Trace:
├─ API Gateway        [0-5ms]
│  └─ Auth Middleware [5-15ms]
│     └─ File Service [15-50ms]
│        ├─ Storage Upload   [50-200ms]  ← 瓶颈！
│        └─ DB Insert        [200-210ms]
└─ Queue Enqueue      [210-215ms]

总耗时: 215ms
```

**数据结构**:
```json
{
  "trace_id": "abc123",
  "spans": [
    {
      "span_id": "span_1",
      "name": "POST /files/upload",
      "start_time": "2024-01-16T10:00:00.000Z",
      "duration_ms": 215,
      "attributes": {
        "http.method": "POST",
        "http.url": "/files/upload",
        "http.status_code": 200,
        "user_id": "user_123",
        "file_size": 1024000
      },
      "children": [...]
    }
  ]
}
```

#### 2. Metrics (指标监控)

**目的**: 聚合统计和实时监控

```python
# 示例：系统指标
file_uploads_total{status="success"} = 12,345
file_uploads_total{status="failed"} = 123

api_request_duration_seconds{
  endpoint="/files/upload",
  method="POST"
} histogram:
  - p50: 0.150
  - p95: 0.450
  - p99: 1.200

redis_queue_length{queue="file_upload"} = 42
```

#### 3. Logs (结构化日志)

**目的**: 详细的上下文信息

```json
{
  "timestamp": "2024-01-16T10:00:00.123Z",
  "level": "INFO",
  "message": "File uploaded successfully",
  "trace_id": "abc123",
  "span_id": "span_1",
  "attributes": {
    "user_id": "user_123",
    "file_id": "file_456",
    "file_size": 1024000,
    "storage_backend": "minio"
  }
}
```

---

### OpenTelemetry 架构模式

#### 架构选择：**混合模式** (Embedded SDK + Service Collector)

```
┌──────────────────────────────────────────────────────────┐
│              Application (FastAPI + Workers)              │
│                                                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │     OpenTelemetry SDK (嵌入式 - Embedded)        │   │
│  │  - 自动 Instrumentation (FastAPI, asyncpg...)    │   │
│  │  - 手动 Instrumentation (业务逻辑)               │   │
│  │  - 上下文传播 (Trace ID, Span ID)                │   │
│  └───────────────────┬──────────────────────────────┘   │
│                      │                                    │
│                      │ OTLP (gRPC/HTTP)                  │
│                      ▼                                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │   OpenTelemetry Collector (服务化 - Service)    │   │
│  │  - 数据接收 (Receivers)                          │   │
│  │  - 数据处理 (Processors: 过滤、采样、聚合)       │   │
│  │  - 数据导出 (Exporters)                          │   │
│  └───────┬────────────┬────────────┬─────────────────┘   │
└──────────┼────────────┼────────────┼─────────────────────┘
           │            │            │
           ▼            ▼            ▼
    ┌───────────┐ ┌──────────┐ ┌──────────┐
    │  Jaeger   │ │Prometheus│ │   Loki   │
    │ (Traces)  │ │(Metrics) │ │  (Logs)  │
    └───────────┘ └──────────┘ └──────────┘
```

#### 嵌入式 (Embedded) vs 服务化 (Service)

| 组件 | 类型 | 作用 | 部署位置 |
|-----|------|------|---------|
| **OpenTelemetry SDK** | 🔹 **嵌入式** | 数据采集、上下文传播 | 应用程序内 (pip install) |
| **OpenTelemetry Collector** | 🔸 **服务化** | 数据处理、路由、导出 | 独立进程/容器 |
| **Backend (Jaeger/Prometheus)** | 🔸 **服务化** | 数据存储、查询、可视化 | 独立服务 |

**示例代码**:

```python
# 1. 嵌入式 SDK（集成到应用代码中）
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# 配置 Tracer Provider
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# 导出到 Collector（gRPC）
otlp_exporter = OTLPSpanExporter(
    endpoint="localhost:4317",  # Collector 地址
    insecure=True
)

trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

# 自动 Instrumentation
FastAPIInstrumentor.instrument_app(app)

# 手动 Instrumentation
@app.post("/files/upload")
async def upload_file(file: UploadFile):
    with tracer.start_as_current_span("upload_file") as span:
        # 自动关联到父 Span
        span.set_attribute("file.name", file.filename)
        span.set_attribute("file.size", file.size)

        result = await file_service.upload(file)
        return result
```

```yaml
# 2. 服务化 Collector（独立进程）
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024

  # 采样（降低存储成本）
  probabilistic_sampler:
    sampling_percentage: 10  # 只保留 10% 的 Trace

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889

  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, probabilistic_sampler]
      exporters: [jaeger]

    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]

    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki]
```

---

## 数据库审计日志深度解析

### 什么是数据库审计日志？

**数据库审计日志** 是将关键业务事件 **持久化** 到关系型数据库的日志记录方式。

#### Unifiles 当前实现

```sql
-- 用户活动日志表
CREATE TABLE unifiles.user_activity_logs (
    id TEXT PRIMARY KEY DEFAULT ('log_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id),
    activity_type TEXT NOT NULL,  -- 'file_upload', 'file_delete', 'api_call'
    activity_details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 任务日志表
CREATE TABLE unifiles.task_logs (
    id TEXT PRIMARY KEY DEFAULT ('tlog_' || encode(gen_random_bytes(16), 'hex')),
    task_id TEXT NOT NULL REFERENCES unifiles.processing_tasks(id),
    log_level TEXT NOT NULL,  -- 'INFO', 'WARNING', 'ERROR'
    message TEXT NOT NULL,
    log_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 典型使用场景

```python
# 记录用户活动
async def log_user_activity(
    user_id: str,
    activity_type: str,
    details: dict,
    ip: str,
    user_agent: str
):
    await db.execute("""
        INSERT INTO unifiles.user_activity_logs
        (user_id, activity_type, activity_details, ip_address, user_agent)
        VALUES ($1, $2, $3, $4, $5)
    """, user_id, activity_type, json.dumps(details), ip, user_agent)

# 查询用户历史活动
async def get_user_activities(user_id: str, limit: int = 100):
    return await db.fetch("""
        SELECT *
        FROM unifiles.user_activity_logs
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
    """, user_id, limit)
```

---

## 两者关系与差异

### 核心差异对比表

| 维度 | OpenTelemetry | PostgreSQL 审计日志 |
|-----|---------------|-------------------|
| **定位** | 🔍 **可观测性** (Observability) | 📜 **合规性/审计** (Compliance/Audit) |
| **主要目的** | 性能监控、故障诊断、系统优化 | 安全审计、合规追溯、法律证据 |
| **目标用户** | 开发者、运维、SRE | 安全团队、审计员、法务 |
| **数据类型** | Traces (调用链), Metrics (指标), Logs (运维日志) | 业务事件、用户行为、敏感操作 |
| **数据量级** | 🔥 **海量** (每秒百万级事件) | 🌊 **中等** (每秒千级事件) |
| **查询模式** | 时间序列查询、聚合统计、分布式追踪 | 精确查询、范围查询、关联查询 |
| **存储周期** | 短期 (7-30 天) | 长期 (1-7 年，甚至永久) |
| **数据完整性** | ⚠️ **允许采样/丢失** (成本优化) | ✅ **必须完整** (合规要求) |
| **事务支持** | ❌ 无需事务 | ✅ **需要事务** (与业务数据一致) |
| **查询性能** | 🚀 **极快** (时间序列数据库优化) | 🐢 **较慢** (关系型数据库) |
| **存储成本** | 💰 **高** (海量数据) | 💵 **中** (数据量可控) |
| **扩展性** | 水平扩展 (分片、集群) | 垂直扩展 (读写分离、分区) |
| **架构模式** | **嵌入式 SDK + 服务化 Collector** | **嵌入式** (数据库即服务) |

---

### 数据流对比

#### OpenTelemetry 数据流

```
用户请求
   ↓
API (自动 Instrumentation)
   ↓ 生成 Trace ID: abc123, Span ID: span_1
调用 FileService
   ↓ Span ID: span_2 (parent: span_1)
调用 StorageService
   ↓ Span ID: span_3 (parent: span_2)
上传到 MinIO
   ↓
所有 Span 批量发送到 Collector
   ↓
Collector 采样 (10%) + 导出
   ↓
Jaeger (存储 Trace)
   ↓
开发者查询 Jaeger UI：
"为什么这个请求耗时 2 秒？"
→ 发现: StorageService 耗时 1.8s (瓶颈！)
```

#### PostgreSQL 审计日志数据流

```
用户请求
   ↓
API 验证权限
   ↓
BEGIN TRANSACTION;  ← 开启事务
   ↓
INSERT INTO files (id, user_id, filename, ...)
   ↓
INSERT INTO user_activity_logs (  ← 记录审计日志
    user_id,
    activity_type = 'file_upload',
    activity_details = '{"file_id": "file_456", "filename": "secret.pdf"}',
    ip_address = '192.168.1.100',
    user_agent = 'Chrome/120.0'
)
   ↓
COMMIT;  ← 提交事务（原子性保证）
   ↓
审计员查询：
"用户 user_123 在 2024-01-15 上传了什么文件？"
→ 精确查询审计日志，导出 CSV 给监管部门
```

---

### 典型使用场景对比

| 场景 | OpenTelemetry | PostgreSQL 审计日志 | 原因 |
|-----|---------------|-------------------|-----|
| **性能分析** | ✅ **最佳** | ❌ 不适用 | 需要分布式追踪和时间聚合 |
| **故障排查** | ✅ **最佳** | ⚠️ 辅助 | 需要调用链和上下文关联 |
| **安全审计** | ⚠️ 辅助 | ✅ **最佳** | 需要完整、可追溯、不可篡改 |
| **合规报告** | ❌ 不适用 | ✅ **最佳** | 监管要求持久化、SQL 查询 |
| **用户行为分析** | ⚠️ 可用 | ✅ **最佳** | 需要精确查询和关联分析 |
| **实时告警** | ✅ **最佳** | ❌ 不适用 | 需要高频指标和阈值监控 |
| **法律取证** | ❌ 不适用 | ✅ **最佳** | 需要长期存储和完整性保证 |
| **成本分析** | ✅ **最佳** | ⚠️ 可用 | 需要聚合计算和多维分析 |

---

## 替换方案利弊分析

### 方案 A: 用 OpenTelemetry 完全替换数据库日志

#### 架构变化

```diff
- 当前架构:
  API → DB (INSERT INTO user_activity_logs)

+ 替换后架构:
  API → OTel SDK → Collector → Loki/ElasticSearch
```

#### ❌ 主要缺点（致命）

1. **丧失事务一致性**
   ```python
   # 当前: 事务保证一致性
   async with db.transaction():
       await db.execute("INSERT INTO files ...")
       await db.execute("INSERT INTO user_activity_logs ...")  # 原子性

   # 替换后: 无事务保证
   await db.execute("INSERT INTO files ...")
   otel_logger.info("file_uploaded", ...)  # 异步发送，可能丢失！

   # 风险: 文件创建成功，但日志丢失 → 审计漏洞
   ```

2. **合规风险**
   ```
   监管要求:
   - GDPR: 用户数据操作必须可追溯，保存 7 年
   - SOC 2: 审计日志不可篡改，必须持久化
   - HIPAA: 敏感数据访问必须完整记录

   OpenTelemetry Loki:
   - 数据采样 (10%) → 90% 日志丢失 ❌
   - 保留期 30 天 → 不满足 7 年要求 ❌
   - 无 ACID 保证 → 可能丢失或乱序 ❌
   ```

3. **查询能力下降**
   ```sql
   -- 当前: 复杂 SQL 查询
   SELECT
       u.username,
       COUNT(*) as upload_count,
       SUM((activity_details->>'file_size')::BIGINT) as total_bytes
   FROM user_activity_logs l
   JOIN users u ON l.user_id = u.id
   WHERE l.activity_type = 'file_upload'
   AND l.created_at > NOW() - INTERVAL '30 days'
   GROUP BY u.username
   HAVING COUNT(*) > 100
   ORDER BY total_bytes DESC;

   -- 替换后: LogQL (Loki 查询语言) - 能力有限
   {job="unifiles"} |= "file_upload" | json | count_over_time[30d]
   # 无法 JOIN users 表 ❌
   # 无法聚合 file_size ❌
   ```

4. **成本增加**
   ```
   当前 PostgreSQL:
   - 1TB 审计日志 (1 年) = $100/月 (存储)

   OpenTelemetry + Loki:
   - 1TB 日志 (1 年) = $500/月 (Loki 存储)
   - Collector 实例 = $100/月
   - Grafana Cloud = $200/月
   总计: $800/月 (8 倍成本！)
   ```

#### ✅ 优点（有限）

1. **性能提升**（对高频日志）
   - 异步发送，不阻塞业务
   - 批量处理，减少数据库压力

2. **统一可观测性平台**
   - Traces + Metrics + Logs 集中查看
   - 自动关联 Trace ID

---

### 方案 B: 混合架构（推荐）

**核心思想**: OpenTelemetry 和数据库日志 **各司其职，优势互补**

```
┌─────────────────────────────────────────────────────┐
│                  Application Layer                   │
└──────────┬──────────────────────────┬────────────────┘
           │                          │
  业务审计日志（低频）           运维日志（高频）
           │                          │
           ▼                          ▼
   ┌───────────────┐         ┌─────────────────┐
   │  PostgreSQL   │         │  OpenTelemetry  │
   │ Audit Logs    │         │  (OTel)         │
   └───────────────┘         └─────────────────┘
           │                          │
           │                          ├─ Traces → Jaeger
           │                          ├─ Metrics → Prometheus
           │                          └─ Logs → Loki
           │
           └─ 合规报告
              └─ 安全审计
                 └─ 法律取证
```

#### 职责划分

| 日志类型 | 存储位置 | 示例 | 保留期 |
|---------|---------|------|--------|
| **业务审计** | PostgreSQL | 用户登录、文件上传/删除、权限变更、支付 | 1-7 年 |
| **系统运维** | OpenTelemetry | API 调用、数据库查询、缓存命中率、队列长度 | 7-30 天 |
| **性能追踪** | OpenTelemetry | 分布式 Trace、Span、耗时统计 | 7-30 天 |
| **错误日志** | **两者都有** | 业务错误 → DB, 系统错误 → OTel | 根据类型 |

#### 实现示例

```python
# 混合日志记录
from opentelemetry import trace
from loguru import logger

tracer = trace.get_tracer(__name__)

@app.post("/files/upload")
async def upload_file(file: UploadFile, user: User):
    # 1. OpenTelemetry Trace（性能监控）
    with tracer.start_as_current_span("upload_file") as span:
        span.set_attribute("user.id", user.id)
        span.set_attribute("file.size", file.size)

        # 2. 业务逻辑
        async with db.transaction():
            # 创建文件记录
            file_record = await db.execute("""
                INSERT INTO files (id, user_id, filename, size_bytes)
                VALUES ($1, $2, $3, $4)
                RETURNING *
            """, file_id, user.id, file.filename, file.size)

            # 3. 数据库审计日志（合规性）
            await db.execute("""
                INSERT INTO user_activity_logs
                (user_id, activity_type, activity_details, ip_address, user_agent)
                VALUES ($1, 'file_upload', $2, $3, $4)
            """, user.id, json.dumps({
                "file_id": file_id,
                "filename": file.filename,
                "size_bytes": file.size,
                "storage_backend": "minio"
            }), request.client.host, request.headers.get("user-agent"))

        # 4. OpenTelemetry 结构化日志（运维）
        logger.info(
            "File uploaded successfully",
            extra={
                "trace_id": span.get_span_context().trace_id,
                "user_id": user.id,
                "file_id": file_id,
                "file_size": file.size
            }
        )

        return {"file_id": file_id}
```

---

## 推荐架构方案

### 最佳实践：三层日志架构

```
Layer 1: 业务审计层 (PostgreSQL)
    ↓ 用途: 合规、审计、法律
    ↓ 特点: 完整、持久、事务性
    ↓ 保留: 1-7 年
    ↓
Layer 2: 运维监控层 (OpenTelemetry)
    ↓ 用途: 性能、故障、优化
    ↓ 特点: 海量、采样、实时
    ↓ 保留: 7-30 天
    ↓
Layer 3: 应用日志层 (Loguru/Structlog)
    ↓ 用途: 开发调试、问题排查
    ↓ 特点: 结构化、上下文丰富
    ↓ 保留: 3-7 天
```

#### 架构图

```
┌────────────────────────────────────────────────────────────┐
│                      Application                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Loguru     │  │ OTel SDK     │  │  DB Client   │    │
│  │ (开发日志)   │  │ (可观测性)   │  │  (审计日志)  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌──────────┐      ┌──────────────┐   ┌──────────────┐
   │  Stdout  │      │ OTel Collector│   │ PostgreSQL   │
   │  /File   │      │               │   │ audit_logs   │
   └──────────┘      └───┬──────┬────┘   └──────────────┘
                         │      │
                         ▼      ▼
                    ┌──────┐ ┌──────┐
                    │Jaeger│ │ Loki │
                    └──────┘ └──────┘
```

---

## 实施指南

### 步骤 1: 保留数据库审计日志（不变）

```sql
-- 必须保留的审计日志表
CREATE TABLE unifiles.user_activity_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- 新增: 关联 Trace ID（用于关联 OpenTelemetry）
    trace_id TEXT,
    span_id TEXT
);

-- 索引优化
CREATE INDEX idx_activity_user_time ON user_activity_logs(user_id, created_at DESC);
CREATE INDEX idx_activity_type_time ON user_activity_logs(activity_type, created_at DESC);
CREATE INDEX idx_activity_trace ON user_activity_logs(trace_id) WHERE trace_id IS NOT NULL;
```

### 步骤 2: 集成 OpenTelemetry（新增）

```python
# unifiles/core/observability/__init__.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

def init_opentelemetry(app, service_name: str = "unifiles-api"):
    """初始化 OpenTelemetry"""

    # 1. 配置 Resource (服务标识)
    resource = Resource(attributes={
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": "production"
    })

    # 2. 配置 Tracer Provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # 3. 配置 Exporter (导出到 Collector)
    otlp_exporter = OTLPSpanExporter(
        endpoint="localhost:4317",  # Collector gRPC 端点
        insecure=True
    )

    provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # 4. 自动 Instrumentation
    FastAPIInstrumentor.instrument_app(app)
    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()

    return trace.get_tracer(__name__)
```

```python
# unifiles/app/main.py
from unifiles.core.observability import init_opentelemetry

app = FastAPI()

# 初始化 OpenTelemetry
tracer = init_opentelemetry(app, service_name="unifiles-api")
```

### 步骤 3: 混合日志记录策略

```python
# unifiles/core/logging/audit.py
from opentelemetry import trace
from typing import Dict, Any, Optional

class AuditLogger:
    """混合审计日志记录器"""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.tracer = trace.get_tracer(__name__)

    async def log_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any],
        ip_address: str,
        user_agent: str,
        conn = None  # 支持事务
    ):
        """记录用户活动（数据库 + OTel）"""

        # 1. 获取当前 Trace 上下文
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        trace_id = format(span_context.trace_id, '032x') if span_context.is_valid else None
        span_id = format(span_context.span_id, '016x') if span_context.is_valid else None

        # 2. 写入数据库（事务性、持久化）
        db = conn or self.db_pool

        await db.execute("""
            INSERT INTO unifiles.user_activity_logs
            (user_id, activity_type, activity_details, ip_address, user_agent, trace_id, span_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, user_id, activity_type, json.dumps(details), ip_address, user_agent, trace_id, span_id)

        # 3. 添加 OTel 事件（用于实时监控）
        current_span.add_event(
            name=f"audit.{activity_type}",
            attributes={
                "user.id": user_id,
                "activity.type": activity_type,
                "activity.details": json.dumps(details),
                "client.ip": ip_address
            }
        )
```

### 步骤 4: 部署 OpenTelemetry Collector

```yaml
# docker-compose.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP
      - "8889:8889"  # Prometheus exporter

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "14250:14250"  # gRPC

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
```

---

## 总结和建议

### 核心结论

**❌ 不应该用 OpenTelemetry 替换数据库审计日志**

原因:
1. 丧失事务一致性（致命）
2. 违反合规要求（致命）
3. 查询能力下降（严重）
4. 成本大幅增加（严重）

**✅ 应该采用混合架构**

```
业务审计 → PostgreSQL (必须保留)
运维监控 → OpenTelemetry (新增)
应用日志 → Loguru/Structlog (现有)
```

---

### 明确回答用户问题

#### 问题 1: 替换有什么利弊？

**利**:
- ✅ 性能提升（高频日志异步处理）
- ✅ 统一可观测性平台

**弊**（致命）:
- ❌ 合规风险（无法满足审计要求）
- ❌ 数据完整性丧失（采样导致丢失）
- ❌ 事务一致性丧失（业务数据与日志分离）
- ❌ 查询能力下降（无法复杂 SQL）
- ❌ 成本增加（8 倍存储成本）

**结论**: **弊远大于利，不建议替换**

---

#### 问题 2: OpenTelemetry 是服务化还是嵌入式？

**答案**: **混合模式**

- **嵌入式部分** (Embedded SDK):
  ```python
  # 集成到应用代码
  pip install opentelemetry-api opentelemetry-sdk

  from opentelemetry import trace
  tracer = trace.get_tracer(__name__)

  with tracer.start_as_current_span("my_operation"):
      # 业务逻辑
      pass
  ```

- **服务化部分** (Service Collector):
  ```yaml
  # 独立进程/容器
  docker run -p 4317:4317 otel/opentelemetry-collector
  ```

**类比**:
```
OpenTelemetry = 嵌入式传感器 (SDK) + 中央处理站 (Collector)

就像智能家居:
- 温度传感器（嵌入式）→ 采集数据
- 智能网关（服务化）→ 数据处理、转发
```

---

### 最终推荐方案

```python
# 1. 保留数据库审计日志（合规）
await audit_logger.log_activity(
    user_id=user.id,
    activity_type="file_upload",
    details={"file_id": file_id},
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent")
)

# 2. 集成 OpenTelemetry（监控）
with tracer.start_as_current_span("upload_file"):
    span.set_attribute("file.size", file.size)
    result = await upload_to_storage(file)

# 3. 应用日志（调试）
logger.info(
    "File uploaded",
    file_id=file_id,
    user_id=user.id
)
```

**三者协同，各司其职！** 🎯

---

**文档结束**
