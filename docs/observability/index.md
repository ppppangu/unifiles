# Observability

可观测性（Observability）是 Unifiles 架构设计的核心考虑之一。通过完善的日志、监控和追踪系统，您可以深入了解系统运行状态，快速定位问题。

## 可观测性三大支柱

### 📝 日志（Logging）
结构化日志记录系统的所有重要事件和操作。

- [日志策略](logging-strategy.md) - 日志设计原则和实施策略
- [统一日志系统](logging-design.md) - 完整的日志系统设计
- [实施状态](implementation-status.md) - 当前实施进度

### 📊 指标（Metrics）
收集和监控系统的性能指标和业务指标。

- API 请求数量和延迟
- 文件处理队列长度
- 数据库连接池使用率
- Worker 任务处理速度

[监控配置指南（待补充）]

### 🔍 追踪（Tracing）
分布式请求追踪，了解请求在系统中的完整路径。

- [OpenTelemetry 集成](otel-instrumentation.md) - 分布式追踪实施
- Trace ID 传播
- Span 生命周期管理
- 性能瓶颈分析

## 统一日志系统

### 日志级别

```python
DEBUG   # 详细的调试信息
INFO    # 常规信息（默认级别）
WARNING # 警告信息
ERROR   # 错误信息
CRITICAL # 严重错误
```

### 日志格式

所有日志采用 JSON 格式，便于机器解析和搜索：

```json
{
  "timestamp": "2025-01-04T10:30:00.123Z",
  "level": "INFO",
  "logger": "unifiles.core.services.file_service",
  "message": "File uploaded successfully",
  "context": {
    "user_id": "uuid-here",
    "file_id": "uuid-here",
    "file_size": 1024000,
    "duration_ms": 125
  },
  "trace_id": "abc123...",
  "span_id": "def456..."
}
```

### 日志存储

- **开发环境**：控制台输出 + 本地文件
- **生产环境**：数据库持久化 + 日志聚合系统

[详细设计](logging-design.md)

## OpenTelemetry 集成

### Trace 传播

每个 HTTP 请求会生成一个 Trace ID，在整个处理流程中传播：

```
HTTP Request (Trace ID: abc123)
  ├─ API Handler (Span: api.upload)
  ├─ File Service (Span: service.store)
  │   ├─ MinIO Upload (Span: storage.put)
  │   └─ Database Insert (Span: db.insert)
  └─ Queue Submit (Span: queue.submit)
```

### 自动化注入

使用 OpenTelemetry Auto-instrumentation 自动追踪：

- HTTP 请求（FastAPI）
- 数据库查询（asyncpg）
- Redis 操作（aioredis）
- HTTP 客户端调用（httpx）

[实施指南](otel-instrumentation.md)

## 监控指标

### 系统指标

- CPU 使用率
- 内存使用率
- 磁盘 I/O
- 网络流量

### 应用指标

#### API 指标
- 请求速率（RPS）
- 响应时间（P50, P95, P99）
- 错误率
- 并发连接数

#### 处理指标
- 文件处理队列长度
- 处理任务成功率
- 处理平均耗时
- OCR 识别准确率

#### 数据库指标
- 连接池使用率
- 查询响应时间
- 慢查询数量
- 锁等待时间

### 业务指标

- 文件上传数量（按类型、大小）
- 知识库创建数量
- 搜索请求数量
- 用户活跃度

## 告警配置

### 告警规则

```yaml
# 高优先级告警
- name: API 服务不可用
  expr: up{job="unifiles"} == 0
  for: 1m
  severity: critical

- name: 错误率过高
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  severity: warning

# 中优先级告警
- name: 响应时间过长
  expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1
  for: 10m
  severity: warning

- name: 队列堆积
  expr: queue_length{queue="extraction"} > 1000
  for: 15m
  severity: warning
```

### 告警通道

- Email
- Slack
- PagerDuty
- 自定义 Webhook

## 可视化

### Grafana 仪表板

预配置的 Grafana 仪表板包括：

1. **系统概览**
   - 服务健康状态
   - 核心指标趋势
   - 告警状态

2. **API 监控**
   - 请求速率和延迟
   - 错误率
   - 端点性能排行

3. **处理流程**
   - 任务队列状态
   - 处理吞吐量
   - 处理成功率

4. **资源使用**
   - 数据库连接池
   - Redis 内存使用
   - MinIO 存储空间

## 日志查询

### 查询示例

```sql
-- 查询最近的错误日志
SELECT * FROM unified_logs
WHERE level = 'ERROR'
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 100;

-- 查询特定用户的操作日志
SELECT * FROM unified_logs
WHERE context->>'user_id' = 'uuid-here'
  AND timestamp > NOW() - INTERVAL '1 day'
ORDER BY timestamp DESC;

-- 查询慢请求（超过1秒）
SELECT * FROM unified_logs
WHERE logger LIKE 'unifiles.app.%'
  AND (context->>'duration_ms')::int > 1000
ORDER BY (context->>'duration_ms')::int DESC
LIMIT 50;
```

## 性能分析

### 使用 Jaeger 分析请求链路

1. 访问 Jaeger UI: `http://localhost:16686`
2. 选择 Service: `unifiles`
3. 搜索 Trace ID 或使用过滤条件
4. 查看详细的 Span 时间线
5. 识别性能瓶颈

### 使用 Pyroscope 进行性能剖析

```bash
# 启动 Pyroscope agent
pyroscope exec python -m unifiles.app.main
```

## 实施状态

当前可观测性功能的实施进度：

- ✅ 统一日志系统设计
- ✅ OpenTelemetry 基础集成
- ✅ 日志数据库持久化
- ✅ Trace ID 传播
- 🚧 Grafana 仪表板配置
- 🚧 告警规则完善
- 📋 日志查询 API
- 📋 自定义指标导出

[详细状态](implementation-status.md)

## 最佳实践

### 日志记录

1. **使用结构化日志**
   ```python
   logger.info("File uploaded", extra={
       "file_id": file_id,
       "file_size": file_size,
       "user_id": user_id
   })
   ```

2. **避免敏感信息**
   - 不记录密码、Token
   - 脱敏处理个人信息

3. **适当的日志级别**
   - DEBUG: 开发调试
   - INFO: 正常业务流程
   - WARNING: 预警信息
   - ERROR: 错误需要关注
   - CRITICAL: 严重问题需要立即处理

### 监控指标

1. **黄金指标**
   - Latency (延迟)
   - Traffic (流量)
   - Errors (错误)
   - Saturation (饱和度)

2. **业务关键指标**
   - 文件处理成功率
   - 搜索准确率
   - 用户满意度

### 追踪

1. **为关键操作添加 Span**
   ```python
   with tracer.start_as_current_span("process_file"):
       # 文件处理逻辑
       pass
   ```

2. **添加有意义的属性**
   ```python
   span.set_attribute("file.size", file_size)
   span.set_attribute("file.type", file_type)
   ```

## 进一步阅读

- [日志策略分析](logging-strategy.md)
- [统一日志系统设计](logging-design.md)
- [OpenTelemetry 实施](otel-instrumentation.md)
- [实施状态](implementation-status.md)
