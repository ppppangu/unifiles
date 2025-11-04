# Unifiles 统一日志系统设计文档

**版本**: v2.0 (简化版)
**日期**: 2025-10-21
**状态**: 架构评审通过
**方案**: 简化混合方案（PostgreSQL + OTEL Traces关联）
**评审评分**: 7.25/10 → 简化后预期 8.5/10

---

## 目录

1. [架构概述](#1-架构概述)
2. [数据库设计](#2-数据库设计)
3. [写入流程设计](#3-写入流程设计)
4. [读取流程设计](#4-读取流程设计)
5. [性能优化策略](#5-性能优化策略)
6. [API接口设计](#6-api接口设计)
7. [代码实现规范](#7-代码实现规范)
8. [运维和监控](#8-运维和监控)
9. [总结与验收标准](#9-总结与验收标准)
10. [架构评审总结](#10-架构评审总结)

---

## 1. 架构概述

### 1.1 整体架构图（简化版）

```
┌─────────────────────────────────────────────────────────────────┐
│                     业务层（App/Worker/Core）                     │
│                                                                  │
│  logger.info("message", extra={...})  ←─ 统一日志接口            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedLogger (日志门面)                       │
│                                                                  │
│  职责：                                                           │
│  1. 自动注入 trace_id/span_id (关联OTEL Traces)                  │
│  2. 上下文丰富（user_id, file_id, etc.）                          │
│  3. 二路输出（本地/队列）                                         │
│  4. 智能路由决策                                                  │
│  5. ERROR/CRITICAL添加Span Events                               │
└──────────┬─────────────────────┬────────────────────────────────┘
           │                     │
    ┌──────▼──────┐      ┌──────▼──────┐
    │ 1. 本地文件  │      │ 2. Redis队列 │
    │  (Loguru)   │      │             │
    └─────────────┘      └──────┬──────┘
    应急、调试                   │
    所有级别                     │
                                ▼
                    ┌────────────────────┐
                    │ Background Flusher │
                    │  (主进程后台线程)   │
                    │  批量写入PostgreSQL │
                    └──────┬─────────────┘
                           │
                           ▼
              ┌────────────────────┐      ┌───────────────────┐
              │    PostgreSQL      │      │  OTEL Traces      │
              │ unified_logs表     │      │  (Jaeger)         │
              │                    │      │                   │
              │ - 持久化存储        │◄────┤ - 通过trace_id    │
              │ - 查询分析          │      │   关联日志        │
              │ - 30-90天保留       │      │ - 性能分析        │
              └────────────────────┘      └───────────────────┘
```

### 1.2 二路输出策略

| 输出路径 | 用途 | 日志级别 | 数据保留 | 查询方式 | 特点 |
|---------|------|---------|---------|---------|------|
| **1. 本地文件** | 应急、调试 | 所有 | 7天 | grep/tail | 即时可用 |
| **2. PostgreSQL** | 持久化、查询 | INFO+ (按策略) | 30-90天 | SQL/REST API | 关联trace_id |

**关联OTEL Traces**: 通过自动注入的`trace_id`/`span_id`字段，日志可在Jaeger UI中关联查看


┌─────────────────────────────────────────────────────────────────┐
│                       查询流程（读取）                             │
└─────────────────────────────────────────────────────────────────┘

    用户请求
       │
       ▼
┌──────────────────┐
│  FastAPI Router  │  GET /api/v1/logs?level=ERROR&limit=100
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  LogQuery API    │  封装查询逻辑，支持：
└────────┬─────────┘  - 按层次/级别/时间查询
         │            - 按 trace_id 关联查询
         │            - 按业务字段（user_id, file_id）查询
         │            - 全文搜索（消息内容）
         ▼
┌──────────────────┐
│  PostgreSQL      │  利用索引快速查询
└────────┬─────────┘  - 分区裁剪（按时间）
         │            - 索引扫描（按条件）
         │            - GIN 索引（JSONB）
         ▼
    返回 JSON 结果
```

### 1.3 设计原则

| 原则 | 说明 | 实现方式 |
|------|------|---------|
| **异步解耦** | 日志写入不阻塞业务 | Redis 队列 + 后台线程 |
| **批量写入** | 减少数据库压力 | 批量100条或5秒刷新 |
| **智能路由** | 高频日志不入库 | 按层次、级别、频率决策 |
| **自动关联** | 日志与分布式追踪打通 | 自动注入 trace_id/span_id |
| **查询优化** | 快速定位问题 | 分区表 + 多维度索引 |
| **降级策略** | 日志系统故障不影响业务 | 队列失败则仅写本地文件 |

---

## 2. 数据库设计

### 2.1 核心表结构

```sql
-- =====================================================
-- 统一日志表（分区表）
-- =====================================================

CREATE TABLE unifiles.unified_logs (
    -- 主键（高性能自增ID）
    id BIGSERIAL NOT NULL,

    -- 时间戳（分区键，精确到毫秒）
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 日志分类
    service_layer TEXT NOT NULL,          -- 'app' | 'worker' | 'core'
    service_name TEXT NOT NULL,           -- 具体服务名，如 'FileUploadWorker'
    level TEXT NOT NULL,                  -- 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

    -- 日志内容
    message TEXT NOT NULL,                -- 日志消息
    context JSONB DEFAULT '{}',           -- 业务上下文（结构化数据）

    -- OTEL 分布式追踪关联
    trace_id TEXT,                        -- 32位十六进制 OpenTelemetry Trace ID
    span_id TEXT,                         -- 16位十六进制 OpenTelemetry Span ID

    -- 错误信息（仅 ERROR/CRITICAL 级别）
    exception_type TEXT,                  -- 异常类型（如 ValueError）
    exception_message TEXT,               -- 异常消息
    stack_trace TEXT,                     -- 完整堆栈跟踪

    -- 代码位置（便于调试）
    module_name TEXT,                     -- Python 模块路径（如 unifiles.app.main）
    function_name TEXT,                   -- 函数名
    line_number INTEGER,                  -- 行号

    -- 环境信息
    hostname TEXT,                        -- 主机名
    process_id INTEGER,                   -- 进程 ID
    thread_name TEXT,                     -- 线程名

    -- 约束
    CONSTRAINT chk_level CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    CONSTRAINT chk_service_layer CHECK (service_layer IN ('app', 'worker', 'core'))

) PARTITION BY RANGE (timestamp);

-- 创建主键（包含分区键）
ALTER TABLE unifiles.unified_logs ADD PRIMARY KEY (id, timestamp);

-- =====================================================
-- 分区表（按月分区）
-- =====================================================

-- 2025年10月分区
CREATE TABLE unifiles.unified_logs_2025_10 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- 2025年11月分区
CREATE TABLE unifiles.unified_logs_2025_11 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- 2025年12月分区
CREATE TABLE unifiles.unified_logs_2025_12 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 注：后续月份的分区通过定时任务自动创建
```

### 2.2 索引设计（查询性能优化）

```sql
-- =====================================================
-- 索引策略（针对常见查询模式）
-- =====================================================

-- 1. 时间倒序索引（最常用：查询最近日志）
CREATE INDEX idx_logs_timestamp_desc ON unifiles.unified_logs (timestamp DESC);

-- 2. 层次+级别+时间（按服务查询错误）
CREATE INDEX idx_logs_layer_level_time ON unifiles.unified_logs (
    service_layer,
    level,
    timestamp DESC
);

-- 3. trace_id 索引（分布式追踪关联查询）
CREATE INDEX idx_logs_trace_id ON unifiles.unified_logs (trace_id, timestamp ASC)
    WHERE trace_id IS NOT NULL;

-- 4. 错误日志快速查询（部分索引）
CREATE INDEX idx_logs_errors ON unifiles.unified_logs (level, timestamp DESC)
    WHERE level IN ('ERROR', 'CRITICAL');

-- 5. 服务名索引（按具体服务查询）
CREATE INDEX idx_logs_service_name ON unifiles.unified_logs (service_name, timestamp DESC);

-- 6. Context JSONB 索引（业务字段查询）
CREATE INDEX idx_logs_context_gin ON unifiles.unified_logs USING GIN (context jsonb_path_ops);

-- 7. 全文搜索索引（消息内容搜索）
CREATE INDEX idx_logs_message_fts ON unifiles.unified_logs USING GIN (to_tsvector('english', message));

-- =====================================================
-- 索引使用示例
-- =====================================================

-- 查询1：最近100条错误日志（使用 idx_logs_errors）
SELECT * FROM unifiles.unified_logs
WHERE level = 'ERROR'
ORDER BY timestamp DESC
LIMIT 100;

-- 查询2：按 trace_id 查询完整链路（使用 idx_logs_trace_id）
SELECT * FROM unifiles.unified_logs
WHERE trace_id = 'abc123...'
ORDER BY timestamp ASC;

-- 查询3：查询特定用户的日志（使用 idx_logs_context_gin）
SELECT * FROM unifiles.unified_logs
WHERE context @> '{"user_id": "user_123"}'
ORDER BY timestamp DESC
LIMIT 100;

-- 查询4：全文搜索包含"connection failed"的日志（使用 idx_logs_message_fts）
SELECT * FROM unifiles.unified_logs
WHERE to_tsvector('english', message) @@ to_tsquery('english', 'connection & failed')
ORDER BY timestamp DESC
LIMIT 100;
```

### 2.3 辅助函数和视图

```sql
-- =====================================================
-- 1. 自动创建未来月份分区
-- =====================================================

CREATE OR REPLACE FUNCTION unifiles.create_next_month_partition()
RETURNS TEXT AS $$
DECLARE
    next_month_start DATE;
    next_month_end DATE;
    partition_name TEXT;
BEGIN
    -- 计算下个月的开始和结束日期
    next_month_start := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    next_month_end := next_month_start + INTERVAL '1 month';

    -- 生成分区表名
    partition_name := 'unified_logs_' || TO_CHAR(next_month_start, 'YYYY_MM');

    -- 检查分区是否已存在
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'unifiles'
        AND tablename = partition_name
    ) THEN
        -- 创建分区
        EXECUTE format(
            'CREATE TABLE unifiles.%I PARTITION OF unifiles.unified_logs
             FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            next_month_start,
            next_month_end
        );

        RETURN 'Created partition: ' || partition_name;
    ELSE
        RETURN 'Partition already exists: ' || partition_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 定时任务：每月1号自动创建下个月的分区
-- SELECT cron.schedule('create-log-partition', '0 0 1 * *', 'SELECT unifiles.create_next_month_partition()');

-- =====================================================
-- 2. 分级清理旧日志
-- =====================================================

CREATE OR REPLACE FUNCTION unifiles.cleanup_old_logs()
RETURNS JSONB AS $$
DECLARE
    deleted_debug INTEGER;
    deleted_info INTEGER;
    deleted_warning INTEGER;
    deleted_error INTEGER;
    deleted_critical INTEGER;
    total_deleted INTEGER;
    deleted_partitions TEXT[];
BEGIN
    -- 1. 按级别清理日志

    -- DEBUG: 保留 7 天
    DELETE FROM unifiles.unified_logs
    WHERE level = 'DEBUG' AND timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days';
    GET DIAGNOSTICS deleted_debug = ROW_COUNT;

    -- INFO: 保留 30 天
    DELETE FROM unifiles.unified_logs
    WHERE level = 'INFO' AND timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_info = ROW_COUNT;

    -- WARNING: 保留 60 天
    DELETE FROM unifiles.unified_logs
    WHERE level = 'WARNING' AND timestamp < CURRENT_TIMESTAMP - INTERVAL '60 days';
    GET DIAGNOSTICS deleted_warning = ROW_COUNT;

    -- ERROR: 保留 90 天
    DELETE FROM unifiles.unified_logs
    WHERE level = 'ERROR' AND timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
    GET DIAGNOSTICS deleted_error = ROW_COUNT;

    -- CRITICAL: 保留 365 天
    DELETE FROM unifiles.unified_logs
    WHERE level = 'CRITICAL' AND timestamp < CURRENT_TIMESTAMP - INTERVAL '365 days';
    GET DIAGNOSTICS deleted_critical = ROW_COUNT;

    total_deleted := deleted_debug + deleted_info + deleted_warning + deleted_error + deleted_critical;

    -- 2. 删除空的旧分区（3个月前的）
    SELECT ARRAY_AGG(tablename) INTO deleted_partitions
    FROM pg_tables
    WHERE schemaname = 'unifiles'
      AND tablename LIKE 'unified_logs_%'
      AND tablename < 'unified_logs_' || TO_CHAR(CURRENT_DATE - INTERVAL '3 months', 'YYYY_MM');

    IF deleted_partitions IS NOT NULL THEN
        FOREACH partition_name IN ARRAY deleted_partitions LOOP
            EXECUTE 'DROP TABLE IF EXISTS unifiles.' || partition_name;
        END LOOP;
    END IF;

    -- 3. VACUUM 回收空间
    EXECUTE 'VACUUM ANALYZE unifiles.unified_logs';

    RETURN jsonb_build_object(
        'success', true,
        'total_deleted', total_deleted,
        'deleted_by_level', jsonb_build_object(
            'DEBUG', deleted_debug,
            'INFO', deleted_info,
            'WARNING', deleted_warning,
            'ERROR', deleted_error,
            'CRITICAL', deleted_critical
        ),
        'deleted_partitions', COALESCE(deleted_partitions, ARRAY[]::TEXT[]),
        'executed_at', CURRENT_TIMESTAMP
    );
END;
$$ LANGUAGE plpgsql;

-- 定时任务：每天凌晨2点清理旧日志
-- SELECT cron.schedule('cleanup-logs', '0 2 * * *', 'SELECT unifiles.cleanup_old_logs()');

-- =====================================================
-- 3. 查询辅助函数
-- =====================================================

-- 通过 trace_id 查询完整链路
CREATE OR REPLACE FUNCTION unifiles.get_logs_by_trace(p_trace_id TEXT)
RETURNS TABLE (
    log_id BIGINT,
    timestamp TIMESTAMPTZ,
    service_layer TEXT,
    service_name TEXT,
    level TEXT,
    message TEXT,
    context JSONB,
    span_id TEXT,
    exception_type TEXT,
    module_name TEXT,
    function_name TEXT,
    line_number INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        id,
        ul.timestamp,
        ul.service_layer,
        ul.service_name,
        ul.level,
        ul.message,
        ul.context,
        ul.span_id,
        ul.exception_type,
        ul.module_name,
        ul.function_name,
        ul.line_number
    FROM unifiles.unified_logs ul
    WHERE ul.trace_id = p_trace_id
    ORDER BY ul.timestamp ASC;  -- 按时间升序，还原执行顺序
END;
$$ LANGUAGE plpgsql STABLE;

-- 查询服务健康状态（过去1小时）
CREATE OR REPLACE VIEW unifiles.service_health_1h AS
SELECT
    service_layer,
    service_name,
    COUNT(*) as total_logs,
    COUNT(*) FILTER (WHERE level = 'ERROR') as error_count,
    COUNT(*) FILTER (WHERE level = 'CRITICAL') as critical_count,
    COUNT(*) FILTER (WHERE level = 'WARNING') as warning_count,
    ROUND(
        COUNT(*) FILTER (WHERE level IN ('ERROR', 'CRITICAL'))::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as error_rate_percent,
    MAX(timestamp) as last_activity
FROM unifiles.unified_logs
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
GROUP BY service_layer, service_name
ORDER BY error_rate_percent DESC NULLS LAST;

-- 查询日志统计信息
CREATE OR REPLACE FUNCTION unifiles.get_log_stats(
    since_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP - INTERVAL '24 hours'
)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'time_range', jsonb_build_object(
            'from', since_timestamp,
            'to', CURRENT_TIMESTAMP
        ),
        'total_logs', COUNT(*),
        'by_level', (
            SELECT jsonb_object_agg(level, count)
            FROM (
                SELECT level, COUNT(*) as count
                FROM unifiles.unified_logs
                WHERE timestamp >= since_timestamp
                GROUP BY level
            ) level_stats
        ),
        'by_service_layer', (
            SELECT jsonb_object_agg(service_layer, count)
            FROM (
                SELECT service_layer, COUNT(*) as count
                FROM unifiles.unified_logs
                WHERE timestamp >= since_timestamp
                GROUP BY service_layer
            ) layer_stats
        ),
        'error_rate_percent', ROUND(
            COUNT(*) FILTER (WHERE level IN ('ERROR', 'CRITICAL'))::NUMERIC /
            NULLIF(COUNT(*), 0) * 100,
            2
        ),
        'top_errors', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'exception_type', exception_type,
                    'count', error_count,
                    'last_occurrence', last_seen
                )
            )
            FROM (
                SELECT
                    exception_type,
                    COUNT(*) as error_count,
                    MAX(timestamp) as last_seen
                FROM unifiles.unified_logs
                WHERE timestamp >= since_timestamp
                  AND exception_type IS NOT NULL
                GROUP BY exception_type
                ORDER BY error_count DESC
                LIMIT 10
            ) top_errors_data
        ),
        'trace_coverage_percent', ROUND(
            COUNT(*) FILTER (WHERE trace_id IS NOT NULL)::NUMERIC /
            NULLIF(COUNT(*), 0) * 100,
            2
        )
    ) INTO result
    FROM unifiles.unified_logs
    WHERE timestamp >= since_timestamp;

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;
```

### 2.4 数据库注释

```sql
-- 表注释
COMMENT ON TABLE unifiles.unified_logs IS '统一运行时日志表 - 记录app/worker/core三层的系统日志';

-- 列注释
COMMENT ON COLUMN unifiles.unified_logs.service_layer IS '服务层次: app(API层), worker(后台任务), core(核心逻辑)';
COMMENT ON COLUMN unifiles.unified_logs.service_name IS '具体服务名称，如 unifiles-api, FileUploadWorker, EmbeddingService';
COMMENT ON COLUMN unifiles.unified_logs.context IS '业务上下文JSONB，如 {"user_id":"xxx", "file_id":"yyy", "task_id":"zzz"}';
COMMENT ON COLUMN unifiles.unified_logs.trace_id IS 'OpenTelemetry Trace ID (32-char hex)，用于关联分布式追踪';
COMMENT ON COLUMN unifiles.unified_logs.span_id IS 'OpenTelemetry Span ID (16-char hex)，精确到具体span';
COMMENT ON COLUMN unifiles.unified_logs.exception_type IS '异常类型（仅ERROR/CRITICAL），如 ValueError, FileNotFoundError';
COMMENT ON COLUMN unifiles.unified_logs.stack_trace IS '完整Python堆栈跟踪（仅ERROR/CRITICAL）';
```

---

## 3. 写入流程设计 (简化版)

### 3.1 为什么需要OTEL Logs

| 需求 | PostgreSQL方案 | OTEL Logs方案 | 结论 |
|------|---------------|--------------|------|
| **持久化存储** | ✅ 优秀（30-90天） | ⚠️ 一般（取决于后端） | PostgreSQL更合适 |
| **查询分析** | ✅ SQL查询强大 | ⚠️ 基础查询 | PostgreSQL更合适 |
| **分布式追踪** | ⚠️ 需手动关联 | ✅ 自动关联Traces | **OTEL更合适** |
| **统一可观测性** | ❌ 独立系统 | ✅ Traces+Metrics+Logs | **OTEL更合适** |
| **实时监控** | ⚠️ 需轮询 | ✅ 实时流式 | **OTEL更合适** |

**结论**：两者互补，PostgreSQL用于持久化查询，OTEL用于实时监控和分布式追踪。

### 3.2 OTEL Logs架构

```
UnifiedLogger
    │
    ├─> emit_otel_log() ─────────────────────────┐
    │                                             │
    │                                             ▼
    │                                ┌─────────────────────────┐
    │                                │ OTELLoggerProvider      │
    │                                │                         │
    │                                │ - LogRecord 格式化       │
    │                                │ - 自动注入 trace context │
    │                                │ - 批量处理               │
    │                                └────────┬────────────────┘
    │                                         │
    │                                         ▼
    │                                ┌─────────────────────────┐
    │                                │ OTLPLogExporter         │
    │                                │                         │
    │                                │ - gRPC 发送             │
    │                                │ - 批量发送（512条）      │
    │                                │ - 失败重试               │
    │                                └────────┬────────────────┘
    │                                         │
    │                                         ▼
    │                                ┌─────────────────────────┐
    │                                │ OTLP Collector          │
    │                                │                         │
    │                                │ - 接收OTLP数据          │
    │                                │ - 处理/过滤/路由         │
    │                                └────────┬────────────────┘
    │                                         │
    │                                         ├────────────────┐
    │                                         ▼                ▼
    │                                 ┌──────────────┐  ┌────────────┐
    │                                 │   Jaeger     │  │   Loki     │
    │                                 │ (Traces+Logs)│  │  (Logs)    │
    │                                 └──────────────┘  └────────────┘
```

### 3.3 OTEL Logs vs Span Events

| 特性 | Span Events | OTEL Logs |
|------|------------|-----------|
| **用途** | Span内的事件标记 | 独立的日志记录 |
| **数据模型** | 简化版（name+attributes） | 完整LogRecord |
| **存储** | 与Span一起存储 | 独立存储 |
| **查询** | 通过trace_id查询Span | 独立查询 + trace关联 |
| **适用场景** | 关键业务节点 | 所有日志 |

**我们的方案**：
- **Span Events**：仅ERROR/CRITICAL级别（关键错误）
- **OTEL Logs**：INFO及以上（可配置）

### 3.4 配置说明

```python
# Unifiles/config/settings.py

class LoggingSettings(BaseSettings):
    """日志配置"""

    # 本地文件
    log_dir: str = Field(default="logs", description="日志目录")
    log_file_rotation: str = Field(default="100 MB", description="文件轮转大小")
    log_file_retention: str = Field(default="7 days", description="文件保留期")

    # PostgreSQL
    db_enabled: bool = Field(default=True, description="启用数据库日志")
    async_batch_size: int = Field(default=100, description="批量写入大小")
    async_flush_interval: int = Field(default=5, description="刷新间隔(秒)")

    # OTEL Logs（新增）
    otel_logs_enabled: bool = Field(default=False, description="启用OTEL Logs")
    otel_logs_endpoint: str = Field(default="localhost:4317", description="OTLP端点")
    otel_logs_min_level: str = Field(default="INFO", description="OTEL最低级别")
    otel_logs_batch_size: int = Field(default=512, description="OTEL批量大小")
    otel_logs_timeout_ms: int = Field(default=30000, description="OTLP超时(ms)")

    # 分层级别
    app_min_level: str = Field(default="INFO", description="App层最低级别")
    worker_min_level: str = Field(default="INFO", description="Worker层最低级别")
    core_min_level: str = Field(default="WARNING", description="Core层最低级别")

    # 采样率
    core_info_sample_rate: float = Field(default=0.1, description="Core层INFO采样率")

    model_config = SettingsConfigDict(env_prefix="LOG_")
```

### 3.5 环境变量配置

```.env
# 日志配置

# 本地文件
LOG_DIR=logs
LOG_FILE_ROTATION=100 MB
LOG_FILE_RETENTION=7 days

# PostgreSQL
LOG_DB_ENABLED=true
LOG_ASYNC_BATCH_SIZE=100
LOG_ASYNC_FLUSH_INTERVAL=5

# OTEL Logs（新增）
LOG_OTEL_LOGS_ENABLED=true
LOG_OTEL_LOGS_ENDPOINT=localhost:4317
LOG_OTEL_LOGS_MIN_LEVEL=INFO
LOG_OTEL_LOGS_BATCH_SIZE=512
LOG_OTEL_LOGS_TIMEOUT_MS=30000

# 分层级别
LOG_APP_MIN_LEVEL=INFO
LOG_WORKER_MIN_LEVEL=INFO
LOG_CORE_MIN_LEVEL=WARNING

# 采样率
LOG_CORE_INFO_SAMPLE_RATE=0.1

# OpenTelemetry基础配置（复用现有配置）
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
OTEL_SAMPLING_RATIO=1.0
```

### 3.6 OTEL Logs实现代码

```python
# Unifiles/core/logging/otel_logs.py

"""
OTEL Logs集成 - OpenTelemetry Logs Signal

提供：
1. OTELLoggerProvider初始化
2. LogRecord发送到OTLP Collector
3. 自动关联trace context
"""

from typing import Optional
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from loguru import logger

from unifiles.config.settings import settings


# 全局LoggerProvider
_logger_provider: Optional[LoggerProvider] = None


def init_otel_logs() -> Optional[LoggerProvider]:
    """
    初始化OTEL Logs

    Returns:
        LoggerProvider实例，如果未启用则返回None
    """
    global _logger_provider

    if not settings.logging.otel_logs_enabled:
        logger.info("OTEL Logs disabled")
        return None

    if _logger_provider is not None:
        logger.warning("OTEL Logs already initialized")
        return _logger_provider

    logger.info(f"Initializing OTEL Logs: endpoint={settings.logging.otel_logs_endpoint}")

    # 1. 创建Resource（复用service信息）
    resource = Resource(attributes={
        SERVICE_NAME: settings.app_name,
        SERVICE_VERSION: settings.app_version,
        "deployment.environment": settings.environment,
    })

    # 2. 创建LoggerProvider
    _logger_provider = LoggerProvider(resource=resource)

    # 3. 创建OTLP Exporter
    try:
        otlp_exporter = OTLPLogExporter(
            endpoint=settings.logging.otel_logs_endpoint,
            insecure=True,  # 生产环境应使用TLS
            timeout=settings.logging.otel_logs_timeout_ms,
        )

        # 4. 添加BatchLogRecordProcessor
        _logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                otlp_exporter,
                max_queue_size=2048,
                max_export_batch_size=settings.logging.otel_logs_batch_size,
                schedule_delay_millis=5000,  # 5秒批量发送
            )
        )

        logger.success(
            f"OTEL Logs initialized: endpoint={settings.logging.otel_logs_endpoint}, "
            f"batch_size={settings.logging.otel_logs_batch_size}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize OTEL Logs: {e}")
        _logger_provider = None

    return _logger_provider


def get_otel_logger(name: str):
    """
    获取OTEL Logger

    Args:
        name: Logger名称（通常使用模块名）

    Returns:
        OTEL Logger实例，如果未初始化则返回None
    """
    if _logger_provider is None:
        return None

    return _logger_provider.get_logger(name)


def shutdown_otel_logs():
    """关闭OTEL Logs（应用退出时调用）"""
    global _logger_provider

    if _logger_provider is not None:
        try:
            _logger_provider.shutdown()
            logger.info("OTEL Logs shutdown completed")
        except Exception as e:
            logger.error(f"Error during OTEL Logs shutdown: {e}")
        finally:
            _logger_provider = None
```

### 3.7 UnifiedLogger集成OTEL Logs

```python
# Unifiles/core/logging/unified.py (修改后)

from opentelemetry.sdk._logs import SeverityNumber
from unifiles.core.logging.otel_logs import get_otel_logger

class UnifiedLogger:
    """统一日志记录器（支持OTEL Logs）"""

    def __init__(self, name: str, service_layer: str):
        self.name = name
        self.service_layer = service_layer
        self.queue_service = get_queue_service()

        # OTEL Logger（可选）
        self.otel_logger = get_otel_logger(name)
        self.otel_enabled = self.otel_logger is not None

        # 日志级别映射
        self.severity_map = {
            'DEBUG': SeverityNumber.DEBUG,
            'INFO': SeverityNumber.INFO,
            'WARNING': SeverityNumber.WARN,
            'ERROR': SeverityNumber.ERROR,
            'CRITICAL': SeverityNumber.FATAL,
        }

        # 配置缓存
        self._config_cache = {}
        self._config_cache_time = {}

    async def _log(self, level: str, message: str, extra: Dict):
        """核心日志方法（三路输出）"""

        # 1. 丰富上下文
        enriched = self._enrich_context(extra)

        # 2. 写入本地文件（loguru，所有级别）
        loguru_logger.bind(**enriched).log(level, message)

        # 3. 写入Redis队列 → PostgreSQL（按策略）
        if await self._should_enqueue(level, enriched):
            await self._enqueue_log(level, message, enriched)

        # 4. 发送到OTEL Logs（INFO及以上，可配置）✨ 新增
        if self.otel_enabled and await self._should_emit_otel(level):
            self._emit_otel_log(level, message, enriched)

    async def _should_emit_otel(self, level: str) -> bool:
        """判断是否发送到OTEL Logs"""

        # 检查全局开关
        if not self.otel_enabled:
            return False

        # 检查最低级别
        min_level = await self._get_config_cached(
            'logging.otel_logs_min_level',
            default='INFO'
        )

        level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        return level_priority[level] >= level_priority[min_level]

    def _emit_otel_log(self, level: str, message: str, enriched: Dict):
        """发送日志到OTEL Logs"""

        if not self.otel_logger:
            return

        try:
            # 提取trace context
            trace_id = enriched.get('trace_id')
            span_id = enriched.get('span_id')

            # 将trace_id/span_id从hex转为int
            trace_id_int = int(trace_id, 16) if trace_id else None
            span_id_int = int(span_id, 16) if span_id else None

            # 构建attributes（OTEL格式）
            attributes = {
                'service.layer': enriched.get('service_layer'),
                'service.name': enriched.get('service_name'),
                'code.function': enriched.get('function_name'),
                'code.filepath': enriched.get('module_name'),
                'code.lineno': enriched.get('line_number'),
                'host.name': enriched.get('hostname'),
                'process.pid': enriched.get('process_id'),
                'thread.name': enriched.get('thread_name'),
            }

            # 添加业务上下文
            if 'user_id' in enriched:
                attributes['user.id'] = enriched['user_id']
            if 'file_id' in enriched:
                attributes['file.id'] = enriched['file_id']
            if 'task_id' in enriched:
                attributes['task.id'] = enriched['task_id']

            # 添加异常信息
            if 'exception_type' in enriched:
                attributes['exception.type'] = enriched['exception_type']
                attributes['exception.message'] = enriched.get('exception_message')

            # 发送LogRecord
            self.otel_logger.emit(
                severity_number=self.severity_map[level],
                severity_text=level,
                body=message,
                attributes={k: v for k, v in attributes.items() if v is not None},
                trace_id=trace_id_int,
                span_id=span_id_int,
            )

        except Exception as e:
            # OTEL发送失败不应影响业务
            loguru_logger.debug(f"Failed to emit OTEL log: {e}")
```

### 3.8 应用启动时初始化

```python
# Unifiles/app/main.py

from unifiles.core.logging.otel_logs import init_otel_logs, shutdown_otel_logs

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""

    # 启动时
    logger.info("Starting Unifiles application...")

    # 初始化OTEL Tracing
    init_opentelemetry(
        app=app,
        service_name="unifiles-api",
        environment=settings.environment,
    )

    # 初始化OTEL Logs（新增）
    init_otel_logs()

    # 初始化数据库连接池
    pool_manager = await get_pool_manager()
    await pool_manager.initialize()

    yield

    # 关闭时
    logger.info("Shutting down Unifiles application...")

    # 关闭OTEL Logs
    shutdown_otel_logs()

    # 关闭数据库连接
    await pool_manager.close()
```

### 3.9 OTLP Collector配置

```yaml
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
    timeout: 5s
    send_batch_size: 512

  resource:
    attributes:
      - key: service.name
        action: upsert
        value: unifiles

exporters:
  # Jaeger（Traces + Logs）
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true

  # Loki（Logs only）
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

  # Prometheus（Metrics）
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    # Traces管道
    traces:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [jaeger]

    # Logs管道（新增）
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [jaeger, loki]

    # Metrics管道
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheus]
```

### 3.10 Docker Compose部署

```yaml
# docker-compose.otel.yml

version: '3.8'

services:
  # OTLP Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus metrics
    networks:
      - unifiles

  # Jaeger（Traces + Logs）
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "14250:14250"  # gRPC
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - unifiles

  # Loki（Logs storage）
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - unifiles

  # Grafana（可视化）
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    networks:
      - unifiles

networks:
  unifiles:
    driver: bridge
```

---

## 4. 写入流程设计

### 4.1 写入流程图

```
业务代码调用日志
       │
       ▼
┌──────────────────────────────────────────────┐
│  logger.info("message", extra={...})         │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  UnifiedLogger._log()                        │
│                                              │
│  1. 丰富上下文（注入trace_id/span_id）         │
│  2. 写入本地文件（loguru，所有级别）           │
│  3. 路由决策（是否入队）                      │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
          ┌────────┴────────┐
          │  路由决策逻辑     │
          └────────┬────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
    [不入队]              [入队]
    （高频日志）         （重要日志）
        │                     │
        ▼                     ▼
    结束              ┌──────────────────┐
                      │ Redis LPUSH      │
                      │ queue:logs       │
                      └──────┬───────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ LogWriter Worker │
                    │                  │
                    │ 批量消费（100条） │
                    │ 或 5秒超时       │
                    └──────┬───────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ PostgreSQL       │
                  │ COPY / executemany│
                  └──────────────────┘
```

### 4.2 路由决策逻辑表

| 场景 | 层次 | 级别 | 入队条件 | 说明 |
|------|------|------|---------|------|
| Redis操作 | core | DEBUG | ❌ | 高频，仅本地 |
| DB查询 | core | DEBUG | ❌ | 高频，用Metrics |
| PDF处理开始 | core | INFO | ✅ (important=True) | 关键业务操作 |
| 向量生成完成 | core | INFO | ✅ (important=True) | 关键业务操作 |
| 文件验证失败 | core | WARNING | ✅ | 业务异常 |
| 算法错误 | core | ERROR | ✅ | 必须持久化 |
| 其他Core INFO | core | INFO | 10%概率 | 采样 |
| 任务入队 | worker | INFO | ✅ | 状态变更 |
| 任务进度更新 | worker | INFO | 10%倍数 | 10%, 20%, ..., 100% |
| 任务完成 | worker | INFO | ✅ | 状态变更 |
| 任务重试 | worker | WARNING | ✅ | 需要监控 |
| 用户操作 | app | INFO | ✅ | 审计需求 |
| 认证失败 | app | WARNING | ✅ | 安全事件 |
| 500错误 | app | ERROR | ✅ | 必须追踪 |

### 4.3 UnifiedLogger 核心代码

文件位置: `Unifiles/core/logging/unified.py`

```python
"""
统一日志系统 - 核心实现

特性：
1. 自动注入 trace_id/span_id
2. 智能路由（本地/队列）
3. Redis 队列异步写入
4. 配置驱动
"""

import asyncio
import json
import os
import random
import socket
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger as loguru_logger
from opentelemetry import trace

from unifiles.config.settings import settings, get_runtime_config
from unifiles.core.queue.redis_queue import get_queue_service

# 上下文变量（线程安全）
_ctx_user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
_ctx_file_id: ContextVar[Optional[str]] = ContextVar('file_id', default=None)
_ctx_task_id: ContextVar[Optional[str]] = ContextVar('task_id', default=None)


class UnifiedLogger:
    """统一日志记录器"""

    # 队列名称
    LOG_QUEUE_NAME = "unifiles:queue:logs"

    def __init__(self, name: str, service_layer: str):
        """
        初始化日志记录器

        Args:
            name: 模块名（通常使用 __name__）
            service_layer: 服务层次 ('app' | 'worker' | 'core')
        """
        self.name = name
        self.service_layer = service_layer

        # 获取队列服务
        self.queue_service = get_queue_service()

        # 配置缓存（5秒过期）
        self._config_cache: Dict[str, Any] = {}
        self._config_cache_time: Dict[str, float] = {}

    def _enrich_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """自动注入 trace_id、span_id、环境信息"""

        enriched = extra.copy()

        # 1. OTEL trace 信息
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            enriched['trace_id'] = format(ctx.trace_id, '032x')
            enriched['span_id'] = format(ctx.span_id, '016x')

        # 2. 服务信息
        enriched['service_layer'] = self.service_layer
        enriched['service_name'] = self.name

        # 3. 环境信息
        enriched['hostname'] = socket.gethostname()
        enriched['process_id'] = os.getpid()
        enriched['thread_name'] = threading.current_thread().name

        # 4. 上下文变量
        if user_id := _ctx_user_id.get():
            enriched.setdefault('user_id', user_id)
        if file_id := _ctx_file_id.get():
            enriched.setdefault('file_id', file_id)
        if task_id := _ctx_task_id.get():
            enriched.setdefault('task_id', task_id)

        # 5. 代码位置（通过 loguru 的 frame）
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            enriched['module_name'] = caller_frame.f_globals.get('__name__')
            enriched['function_name'] = caller_frame.f_code.co_name
            enriched['line_number'] = caller_frame.f_lineno

        return enriched

    async def _should_enqueue(self, level: str, enriched: Dict) -> bool:
        """路由决策：是否入队写入数据库"""

        # 1. 全局开关
        db_enabled = await self._get_config_cached('logging.db_enabled', default=True)
        if not db_enabled:
            return False

        # 2. 级别优先级
        level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
        current_priority = level_priority[level]

        # 3. 按层次判断
        if self.service_layer == 'core':
            # Core层：WARNING及以上必入队
            if current_priority >= 2:
                return True
            # INFO级别：标记为重要的入队
            if level == 'INFO' and enriched.get('important', False):
                return True
            # 其他INFO：采样（默认10%）
            if level == 'INFO':
                sample_rate = await self._get_config_cached('logging.core_info_sample_rate', default=0.1)
                return random.random() < sample_rate
            return False

        elif self.service_layer == 'worker':
            # Worker层：任务相关日志
            if 'task_id' in enriched:
                # 进度日志：采样（10%, 20%, ..., 100%）
                if 'progress' in enriched:
                    progress = enriched['progress']
                    return progress % 10 == 0
                # 其他任务日志：INFO及以上
                return current_priority >= 1
            return current_priority >= 2

        elif self.service_layer == 'app':
            # App层：用户操作、认证、ERROR及以上
            if 'user_id' in enriched or 'auth' in enriched.get('operation', ''):
                return current_priority >= 1
            return current_priority >= 2

        return False

    async def _get_config_cached(self, key: str, default: Any) -> Any:
        """带缓存的配置获取（减少Redis查询）"""
        now = time.time()

        if key in self._config_cache:
            if now - self._config_cache_time.get(key, 0) < 5:  # 5秒缓存
                return self._config_cache[key]

        value = await get_runtime_config(key, default)
        self._config_cache[key] = value
        self._config_cache_time[key] = now
        return value

    async def _enqueue_log(self, level: str, message: str, enriched: Dict):
        """将日志入队（Redis队列）"""

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            **enriched
        }

        try:
            # 入队到 Redis
            await self.queue_service.enqueue(
                queue_name=self.LOG_QUEUE_NAME,
                task=log_entry,
                priority=0  # 日志队列不使用优先级
            )
        except Exception as e:
            # 队列失败不应影响业务，仅本地记录
            loguru_logger.error(f"Failed to enqueue log: {e}")

    async def info(self, message: str, **kwargs):
        """记录INFO级别日志"""
        await self._log('INFO', message, kwargs.get('extra', {}))

    async def warning(self, message: str, **kwargs):
        """记录WARNING级别日志"""
        await self._log('WARNING', message, kwargs.get('extra', {}))

    async def error(self, message: str, **kwargs):
        """记录ERROR级别日志（自动捕获异常堆栈）"""
        extra = kwargs.get('extra', {})

        # 自动捕获异常信息
        if exc_info := kwargs.get('exc_info'):
            import traceback
            extra['exception_type'] = type(exc_info).__name__
            extra['exception_message'] = str(exc_info)
            extra['stack_trace'] = ''.join(
                traceback.format_exception(
                    type(exc_info),
                    exc_info,
                    exc_info.__traceback__
                )
            )

        await self._log('ERROR', message, extra)

    async def critical(self, message: str, **kwargs):
        """记录CRITICAL级别日志"""
        await self._log('CRITICAL', message, kwargs.get('extra', {}))

    async def debug(self, message: str, **kwargs):
        """记录DEBUG级别日志（仅本地，不入队）"""
        extra = kwargs.get('extra', {})
        enriched = self._enrich_context(extra)

        # DEBUG级别仅写本地文件
        loguru_logger.bind(**enriched).debug(message)

    async def _log(self, level: str, message: str, extra: Dict):
        """核心日志方法"""

        # 1. 丰富上下文
        enriched = self._enrich_context(extra)

        # 2. 写入本地文件（loguru，所有级别）
        loguru_logger.bind(**enriched).log(level, message)

        # 3. 路由决策：是否入队
        if await self._should_enqueue(level, enriched):
            await self._enqueue_log(level, message, enriched)

        # 4. 添加 OTEL 事件（ERROR/CRITICAL）
        if level in ('ERROR', 'CRITICAL'):
            span = trace.get_current_span()
            if span.is_recording():
                span.add_event(
                    f"log.{level.lower()}",
                    attributes={
                        'log.message': message,
                        'log.level': level,
                        **{k: str(v) for k, v in enriched.items() if k not in ('stack_trace',)}
                    }
                )


# ===== 工厂方法 =====

def get_logger(name: str, service_layer: str = 'core') -> UnifiedLogger:
    """
    获取统一日志记录器

    Args:
        name: 模块名（通常使用 __name__）
        service_layer: 服务层次 ('app' | 'worker' | 'core')

    Returns:
        UnifiedLogger 实例

    使用示例:
        logger = get_logger(__name__, service_layer='worker')
        await logger.info("Task started", extra={"task_id": "123"})
    """
    return UnifiedLogger(name, service_layer)


# ===== 上下文管理器 =====

class LogContext:
    """日志上下文管理器（自动注入user_id等）"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.tokens = {}

    def __enter__(self):
        if 'user_id' in self.kwargs:
            self.tokens['user_id'] = _ctx_user_id.set(self.kwargs['user_id'])
        if 'file_id' in self.kwargs:
            self.tokens['file_id'] = _ctx_file_id.set(self.kwargs['file_id'])
        if 'task_id' in self.kwargs:
            self.tokens['task_id'] = _ctx_task_id.set(self.kwargs['task_id'])
        return self

    def __exit__(self, *args):
        for token in self.tokens.values():
            token.var.reset(token)


def with_context(**kwargs):
    """
    日志上下文（自动注入到所有日志）

    使用示例:
        with with_context(user_id="user_123", file_id="file_456"):
            await logger.info("Processing file")  # 自动包含 user_id 和 file_id
    """
    return LogContext(**kwargs)
```

### 4.4 LogWriter Worker 实现

文件位置: `Unifiles/workers/log_writer_worker.py`

```python
"""
LogWriter Worker - 专用日志写入器

职责：
1. 批量消费 Redis 队列中的日志
2. 批量写入 PostgreSQL
3. 失败重试
4. 性能监控
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

from loguru import logger

from unifiles.core.database.pool_manager import get_pool_manager
from unifiles.workers.base_worker import BaseWorker


class LogWriterWorker(BaseWorker):
    """日志写入器 Worker"""

    def __init__(self):
        super().__init__(
            queue_name="unifiles:queue:logs",
            worker_name="LogWriterWorker",
            concurrency=2,  # 2个并发消费者
            use_priority_queue=False,
        )

        # 批量写入参数
        self.batch_size = 100
        self.batch_timeout = 5.0  # 5秒超时

        # 批次缓冲区
        self.batch: List[Dict[str, Any]] = []
        self.last_flush_time = asyncio.get_event_loop().time()

    async def process_task(self, task: Dict):
        """
        处理单条日志（添加到批次）

        Args:
            task: 日志条目 {timestamp, level, message, ...}
        """
        # 添加到批次
        self.batch.append(task)

        # 判断是否需要刷新
        current_time = asyncio.get_event_loop().time()

        if (
            len(self.batch) >= self.batch_size or
            (current_time - self.last_flush_time) >= self.batch_timeout
        ):
            await self._flush_batch()

    async def _flush_batch(self):
        """批量写入数据库"""

        if not self.batch:
            return

        batch_to_write = self.batch.copy()
        self.batch.clear()
        self.last_flush_time = asyncio.get_event_loop().time()

        try:
            pool_manager = await get_pool_manager()

            async with pool_manager.pg_pool.acquire() as conn:
                # 使用 COPY 或 executemany 批量插入
                await self._batch_insert(conn, batch_to_write)

            logger.info(
                f"Flushed {len(batch_to_write)} logs to database",
                extra={"batch_size": len(batch_to_write)}
            )

        except Exception as e:
            logger.error(
                f"Failed to flush logs batch: {e}",
                extra={"batch_size": len(batch_to_write)},
                exc_info=e
            )

            # 失败重试：重新入队（简化版）
            # 生产环境应该有更完善的重试机制
            for log_entry in batch_to_write:
                try:
                    await self.queue_service.enqueue(
                        queue_name=self.queue_name,
                        task=log_entry
                    )
                except:
                    pass  # 记录到本地文件作为降级

    async def _batch_insert(self, conn, batch: List[Dict]):
        """批量插入数据库"""

        # 准备批量插入数据
        records = []
        for log_entry in batch:
            # 提取字段
            context = {
                k: v for k, v in log_entry.items()
                if k not in (
                    'timestamp', 'level', 'service_layer', 'service_name',
                    'message', 'trace_id', 'span_id', 'exception_type',
                    'exception_message', 'stack_trace', 'module_name',
                    'function_name', 'line_number', 'hostname',
                    'process_id', 'thread_name'
                )
            }

            records.append((
                log_entry.get('timestamp'),
                log_entry.get('level'),
                log_entry.get('service_layer'),
                log_entry.get('service_name'),
                log_entry.get('message'),
                json.dumps(context),
                log_entry.get('trace_id'),
                log_entry.get('span_id'),
                log_entry.get('exception_type'),
                log_entry.get('exception_message'),
                log_entry.get('stack_trace'),
                log_entry.get('module_name'),
                log_entry.get('function_name'),
                log_entry.get('line_number'),
                log_entry.get('hostname'),
                log_entry.get('process_id'),
                log_entry.get('thread_name'),
            ))

        # 批量插入
        await conn.executemany("""
            INSERT INTO unifiles.unified_logs
            (timestamp, level, service_layer, service_name, message, context,
             trace_id, span_id, exception_type, exception_message, stack_trace,
             module_name, function_name, line_number,
             hostname, process_id, thread_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """, records)

    async def on_shutdown(self):
        """Worker关闭时刷新剩余日志"""
        await self._flush_batch()
        await super().on_shutdown()


# ===== 启动 Worker =====

async def main():
    """启动 LogWriter Worker"""
    worker = LogWriterWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 读取流程设计

### 5.1 查询API设计

文件位置: `Unifiles/app/routers/logs.py`

```python
"""
日志查询 API

提供：
1. 基础查询（按时间、层次、级别）
2. trace_id 关联查询
3. 业务字段查询（user_id, file_id, task_id）
4. 全文搜索
5. 统计分析
"""

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
    import time
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
        conditions.append(f"context @> $${param_idx}")
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
    import time
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
```

---

## 6. 性能优化策略

### 6.1 写入性能优化

| 优化点 | 方案 | 效果 |
|--------|------|------|
| **异步解耦** | Redis队列 + Worker | 业务线程不阻塞 |
| **批量写入** | 100条/批或5秒超时 | 减少数据库连接开销 |
| **分区表** | 按月分区 | 提升写入和查询性能 |
| **索引优化** | 部分索引、GIN索引 | 降低写入开销 |
| **连接池** | 复用数据库连接 | 减少连接建立时间 |

### 6.2 查询性能优化

| 优化点 | 方案 | 查询场景 |
|--------|------|---------|
| **分区裁剪** | 按时间范围自动选择分区 | 查询最近日志 |
| **时间倒序索引** | `(timestamp DESC)` | 最常用查询 |
| **复合索引** | `(service_layer, level, timestamp)` | 按服务查错误 |
| **GIN 索引** | JSONB字段 | 按业务字段查询 |
| **全文索引** | `to_tsvector` | 消息内容搜索 |
| **VACUUM** | 定期回收空间 | 保持查询性能 |

### 6.3 性能监控指标

```python
# Worker 性能指标（Prometheus Metrics）

from unifiles.core.observability.metrics import get_metric

# 日志写入速率
get_metric('log_write_rate').labels(worker='LogWriter').inc()

# 批次大小分布
get_metric('log_batch_size').labels(worker='LogWriter').observe(batch_size)

# 写入延迟
get_metric('log_write_latency_ms').labels(worker='LogWriter').observe(latency_ms)

# 队列长度
get_metric('log_queue_length').set(queue_length)
```

---

## 7. API接口设计

完整的 API 规范参见上面的 `logs.py` 代码。

### 7.1 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/logs` | GET | 基础查询（时间、层次、级别、业务字段） |
| `/api/v1/logs/trace/{trace_id}` | GET | 通过trace_id查询完整链路 |
| `/api/v1/logs/stats` | GET | 日志统计信息 |
| `/api/v1/logs/health` | GET | 服务健康状态 |
| `/api/v1/logs/export` | GET | 导出日志（CSV/JSON） |

### 7.2 查询示例

```bash
# 1. 查询最近1小时的错误日志
curl "http://localhost:8088/api/v1/logs?last_hours=1&level=ERROR&limit=50"

# 2. 查询特定用户的操作日志
curl "http://localhost:8088/api/v1/logs?user_id=user_123&limit=100"

# 3. 通过 trace_id 查询完整链路
curl "http://localhost:8088/api/v1/logs/trace/abc123def456..."

# 4. 全文搜索包含"connection failed"的日志
curl "http://localhost:8088/api/v1/logs?search=connection%20failed"

# 5. 查询服务健康状态
curl "http://localhost:8088/api/v1/logs/health"

# 6. 导出日志为CSV
curl "http://localhost:8088/api/v1/logs/export?format=csv&start_time=2025-10-20T00:00:00" -o logs.csv
```

---

## 8. 代码实现规范

### 8.1 使用规范

```python
# ===== App 层 =====
from unifiles.core.logging import get_logger

logger = get_logger(__name__, service_layer='app')

# 用户操作日志（自动入库）
await logger.info(
    "User uploaded file",
    extra={
        "user_id": user_id,
        "file_id": file_id,
        "file_size": file_size,
        "operation": "file_upload"
    }
)

# 认证失败（安全事件，自动入库）
await logger.warning(
    "Authentication failed",
    extra={
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "operation": "auth_failed"
    }
)


# ===== Worker 层 =====
logger = get_logger(__name__, service_layer='worker')

# 任务开始（自动入库）
await logger.info(
    "Task started",
    extra={
        "task_id": task_id,
        "task_type": "file_upload",
        "user_id": user_id
    }
)

# 任务进度（每10%入库，其他仅本地）
await logger.info(
    f"Task progress: {progress}%",
    extra={
        "task_id": task_id,
        "progress": progress  # 10%, 20%, ..., 100% 会入库
    }
)

# 任务失败（自动入库）
await logger.error(
    "Task failed",
    extra={
        "task_id": task_id,
        "retry_count": retry_count
    },
    exc_info=exception
)


# ===== Core 层 =====
logger = get_logger(__name__, service_layer='core')

# 高频操作（仅本地，不入库）
logger.debug(f"Redis cache hit: {cache_key}")
logger.debug(f"DB query executed in {elapsed_ms}ms")

# 关键业务操作（标记 important=True，入库）
await logger.info(
    "PDF processing completed",
    extra={
        "file_id": file_id,
        "pages": page_count,
        "processing_time_ms": elapsed_ms,
        "important": True  # 强制入库
    }
)

# 业务异常（自动入库）
await logger.warning(
    "File validation failed",
    extra={
        "file_id": file_id,
        "validation_error": "Invalid PDF format"
    }
)

# 错误（自动入库）
await logger.error(
    "Embedding generation failed",
    extra={
        "file_id": file_id,
        "model": "text-embedding-3-small"
    },
    exc_info=e
)
```

### 8.2 上下文管理器

```python
from unifiles.core.logging import get_logger, with_context

logger = get_logger(__name__, service_layer='app')

# 自动注入 user_id 到所有日志
with with_context(user_id="user_123"):
    await logger.info("Processing request")  # 自动包含 user_id
    await logger.info("File uploaded")       # 自动包含 user_id
```

---

## 9. 运维和监控

### 9.1 部署清单

```bash
# 1. 数据库迁移
psql -U postgres -d unifiles -f scripts/sql/028-create-unified-logs.sql

# 2. 启动 LogWriter Worker（systemd服务）
sudo systemctl start unifiles-log-writer

# 3. 配置定时任务（cron）
# 每月1号创建下个月分区
0 0 1 * * psql -U postgres -d unifiles -c "SELECT unifiles.create_next_month_partition();"

# 每天凌晨2点清理旧日志
0 2 * * * psql -U postgres -d unifiles -c "SELECT unifiles.cleanup_old_logs();"

# 4. 监控队列长度
# Prometheus监控 unifiles:queue:logs 队列长度
```

### 9.2 监控指标

```yaml
# Prometheus 监控指标

# 日志写入速率
log_write_rate{worker="LogWriter"} 1500/s

# 队列长度
log_queue_length{queue="unifiles:queue:logs"} 250

# Worker 健康状态
worker_alive{name="LogWriter"} 1

# 数据库表大小
pg_table_size_bytes{table="unified_logs"} 5GB
```

### 9.3 告警规则

```yaml
# Prometheus 告警规则

groups:
  - name: logging
    rules:
      # 队列积压告警
      - alert: LogQueueBacklog
        expr: log_queue_length > 10000
        for: 5m
        annotations:
          summary: "日志队列积压超过10000条"

      # Worker 宕机告警
      - alert: LogWriterDown
        expr: worker_alive{name="LogWriter"} == 0
        for: 1m
        annotations:
          summary: "LogWriter Worker 已停止"

      # 错误日志激增告警
      - alert: ErrorLogSpike
        expr: rate(log_write_rate{level="ERROR"}[5m]) > 100
        for: 5m
        annotations:
          summary: "错误日志激增（>100/s）"
```

---

## 10. 总结与验收标准

### 10.1 功能验收

| 功能 | 验收标准 | 测试方法 |
|------|---------|---------|
| **自动trace_id注入** | 100%的ERROR日志包含trace_id | 查询数据库 |
| **异步写入** | 日志调用不阻塞业务（< 1ms） | 性能测试 |
| **批量写入** | Worker批量写入100条或5秒 | 监控Worker日志 |
| **查询性能** | 查询最近100条日志 < 100ms | API性能测试 |
| **trace关联查询** | 通过trace_id查询完整链路 < 200ms | API测试 |
| **配置动态生效** | 修改配置后 < 5秒生效 | 修改Redis配置 |

### 10.2 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 日志写入吞吐量 | > 10000条/秒 | Worker批量写入 |
| 队列消费延迟 | < 5秒 | 队列到数据库 |
| 日志查询延迟 | < 200ms (P95) | 基础查询 |
| 数据库表大小 | < 100GB | 定期清理 |
| Worker CPU使用率 | < 50% | 正常负载 |

### 10.3 可靠性

| 场景 | 降级策略 | 验收 |
|------|---------|------|
| Redis队列故障 | 仅写本地文件 | 业务不受影响 |
| 数据库故障 | Worker重试 + 降级 | 数据不丢失 |
| Worker崩溃 | 自动重启（systemd） | < 10秒恢复 |
| 进程重启 | 刷新剩余批次 | 数据不丢失 |

---

**文档结束**

如需补充或修改，请联系开发团队。
