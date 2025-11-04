-- =====================================================
-- 028: 创建统一日志系统表和函数
-- =====================================================
-- 功能：
--   1. 创建 unified_logs 分区表
--   2. 创建初始月份分区
--   3. 创建索引优化查询性能
--   4. 创建辅助函数和视图
--
-- 设计文档：docs/UNIFIED_LOGGING_SYSTEM_DESIGN.md
-- =====================================================

-- =====================================================
-- 1. 创建核心表结构（分区表）
-- =====================================================

CREATE TABLE IF NOT EXISTS unifiles.unified_logs (
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
-- 2. 创建初始分区（按月分区）
-- =====================================================

-- 2025年10月分区
CREATE TABLE IF NOT EXISTS unifiles.unified_logs_2025_10 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- 2025年11月分区
CREATE TABLE IF NOT EXISTS unifiles.unified_logs_2025_11 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- 2025年12月分区
CREATE TABLE IF NOT EXISTS unifiles.unified_logs_2025_12 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 2026年1月分区
CREATE TABLE IF NOT EXISTS unifiles.unified_logs_2026_01 PARTITION OF unifiles.unified_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- 注：后续月份的分区通过定时任务自动创建

-- =====================================================
-- 3. 创建索引（查询性能优化）
-- =====================================================

-- 1. 时间倒序索引（最常用：查询最近日志）
CREATE INDEX IF NOT EXISTS idx_logs_timestamp_desc ON unifiles.unified_logs (timestamp DESC);

-- 2. 层次+级别+时间（按服务查询错误）
CREATE INDEX IF NOT EXISTS idx_logs_layer_level_time ON unifiles.unified_logs (
    service_layer,
    level,
    timestamp DESC
);

-- 3. trace_id 索引（分布式追踪关联查询）
CREATE INDEX IF NOT EXISTS idx_logs_trace_id ON unifiles.unified_logs (trace_id, timestamp ASC)
    WHERE trace_id IS NOT NULL;

-- 4. 错误日志快速查询（部分索引）
CREATE INDEX IF NOT EXISTS idx_logs_errors ON unifiles.unified_logs (level, timestamp DESC)
    WHERE level IN ('ERROR', 'CRITICAL');

-- 5. 服务名索引（按具体服务查询）
CREATE INDEX IF NOT EXISTS idx_logs_service_name ON unifiles.unified_logs (service_name, timestamp DESC);

-- 6. Context JSONB 索引（业务字段查询）
CREATE INDEX IF NOT EXISTS idx_logs_context_gin ON unifiles.unified_logs USING GIN (context jsonb_path_ops);

-- 7. 全文搜索索引（消息内容搜索）
CREATE INDEX IF NOT EXISTS idx_logs_message_fts ON unifiles.unified_logs USING GIN (to_tsvector('english', message));

-- =====================================================
-- 4. 添加表和列注释
-- =====================================================

COMMENT ON TABLE unifiles.unified_logs IS '统一运行时日志表 - 记录app/worker/core三层的系统日志';

COMMENT ON COLUMN unifiles.unified_logs.service_layer IS '服务层次: app(API层), worker(后台任务), core(核心逻辑)';
COMMENT ON COLUMN unifiles.unified_logs.service_name IS '具体服务名称，如 unifiles-api, FileUploadWorker, EmbeddingService';
COMMENT ON COLUMN unifiles.unified_logs.level IS '日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL';
COMMENT ON COLUMN unifiles.unified_logs.message IS '日志消息内容';
COMMENT ON COLUMN unifiles.unified_logs.context IS '业务上下文JSONB，如 {"user_id":"xxx", "file_id":"yyy", "task_id":"zzz"}';
COMMENT ON COLUMN unifiles.unified_logs.trace_id IS 'OpenTelemetry Trace ID (32-char hex)，用于关联分布式追踪';
COMMENT ON COLUMN unifiles.unified_logs.span_id IS 'OpenTelemetry Span ID (16-char hex)，精确到具体span';
COMMENT ON COLUMN unifiles.unified_logs.exception_type IS '异常类型（仅ERROR/CRITICAL），如 ValueError, FileNotFoundError';
COMMENT ON COLUMN unifiles.unified_logs.exception_message IS '异常消息';
COMMENT ON COLUMN unifiles.unified_logs.stack_trace IS '完整Python堆栈跟踪（仅ERROR/CRITICAL）';
COMMENT ON COLUMN unifiles.unified_logs.module_name IS 'Python模块路径';
COMMENT ON COLUMN unifiles.unified_logs.function_name IS '函数名';
COMMENT ON COLUMN unifiles.unified_logs.line_number IS '代码行号';
COMMENT ON COLUMN unifiles.unified_logs.hostname IS '主机名';
COMMENT ON COLUMN unifiles.unified_logs.process_id IS '进程ID';
COMMENT ON COLUMN unifiles.unified_logs.thread_name IS '线程名';

-- =====================================================
-- 5. 辅助函数：自动创建未来月份分区
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

COMMENT ON FUNCTION unifiles.create_next_month_partition IS '自动创建下个月的日志分区表（用于定时任务）';

-- 定时任务示例（需要 pg_cron 扩展）：
-- SELECT cron.schedule('create-log-partition', '0 0 1 * *', 'SELECT unifiles.create_next_month_partition()');

-- =====================================================
-- 6. 辅助函数：分级清理旧日志
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
    partition_name TEXT;
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

COMMENT ON FUNCTION unifiles.cleanup_old_logs IS '分级清理旧日志（DEBUG 7天, INFO 30天, WARNING 60天, ERROR 90天, CRITICAL 365天）';

-- 定时任务示例（需要 pg_cron 扩展）：
-- SELECT cron.schedule('cleanup-logs', '0 2 * * *', 'SELECT unifiles.cleanup_old_logs()');

-- =====================================================
-- 7. 查询函数：通过 trace_id 查询完整链路
-- =====================================================

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

COMMENT ON FUNCTION unifiles.get_logs_by_trace IS '通过 OpenTelemetry Trace ID 查询完整链路日志';

-- =====================================================
-- 8. 查询函数：获取日志统计信息
-- =====================================================

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

COMMENT ON FUNCTION unifiles.get_log_stats IS '获取指定时间范围内的日志统计信息（级别分布、错误率、Top错误、trace覆盖率）';

-- =====================================================
-- 9. 视图：服务健康状态（过去1小时）
-- =====================================================

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

COMMENT ON VIEW unifiles.service_health_1h IS '过去1小时的服务健康状态（日志数、错误率、最后活动时间）';

-- =====================================================
-- 10. 查询示例和使用说明
-- =====================================================

-- 示例 1: 查询最近100条错误日志（使用 idx_logs_errors）
-- SELECT * FROM unifiles.unified_logs
-- WHERE level = 'ERROR'
-- ORDER BY timestamp DESC
-- LIMIT 100;

-- 示例 2: 按 trace_id 查询完整链路（使用 idx_logs_trace_id）
-- SELECT * FROM unifiles.get_logs_by_trace('abc123...');

-- 示例 3: 查询特定用户的日志（使用 idx_logs_context_gin）
-- SELECT * FROM unifiles.unified_logs
-- WHERE context @> '{"user_id": "user_123"}'
-- ORDER BY timestamp DESC
-- LIMIT 100;

-- 示例 4: 全文搜索包含"connection failed"的日志（使用 idx_logs_message_fts）
-- SELECT * FROM unifiles.unified_logs
-- WHERE to_tsvector('english', message) @@ to_tsquery('english', 'connection & failed')
-- ORDER BY timestamp DESC
-- LIMIT 100;

-- 示例 5: 获取过去24小时的日志统计
-- SELECT unifiles.get_log_stats(CURRENT_TIMESTAMP - INTERVAL '24 hours');

-- 示例 6: 查看服务健康状态
-- SELECT * FROM unifiles.service_health_1h;

-- 示例 7: 手动创建下个月的分区
-- SELECT unifiles.create_next_month_partition();

-- 示例 8: 手动清理旧日志
-- SELECT unifiles.cleanup_old_logs();

-- =====================================================
-- 迁移完成
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '028-create-unified-logs.sql migration completed successfully';
    RAISE NOTICE 'Created unified_logs partitioned table with initial partitions';
    RAISE NOTICE 'Created 7 indexes for query optimization';
    RAISE NOTICE 'Created 4 helper functions and 1 view';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Set up cron job to create monthly partitions: SELECT unifiles.create_next_month_partition();';
    RAISE NOTICE '  2. Set up cron job to cleanup old logs: SELECT unifiles.cleanup_old_logs();';
    RAISE NOTICE '  3. Implement UnifiedLogger in Unifiles/core/logging/unified.py';
    RAISE NOTICE '  4. Implement LogWriter Worker in Unifiles/workers/log_writer_worker.py';
END $$;
