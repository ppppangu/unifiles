-- =====================================================
-- 027: 添加 OpenTelemetry Trace ID 关联
-- =====================================================
-- 功能：
--   1. 为 user_activity_logs 添加 trace_id 和 span_id 字段
--   2. 为 processing_tasks 添加 trace_id 字段（已有 task_logs）
--   3. 创建索引用于通过 trace_id 查询
--   4. 创建辅助函数用于 Trace 关联查询
--
-- 用途：
--   - 从 Jaeger UI 跳转到审计日志详情
--   - 从审计日志查看完整的分布式追踪
--   - 性能分析与合规审计的关联
-- =====================================================

-- =====================================================
-- 1. 修改 user_activity_logs 表
-- =====================================================

-- 添加 trace_id 字段（OpenTelemetry Trace ID，32 位十六进制）
ALTER TABLE unifiles.user_activity_logs
ADD COLUMN IF NOT EXISTS trace_id TEXT;

-- 添加 span_id 字段（OpenTelemetry Span ID，16 位十六进制）
ALTER TABLE unifiles.user_activity_logs
ADD COLUMN IF NOT EXISTS span_id TEXT;

-- 添加索引用于通过 trace_id 快速查询
CREATE INDEX IF NOT EXISTS idx_user_activity_logs_trace_id
ON unifiles.user_activity_logs(trace_id)
WHERE trace_id IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN unifiles.user_activity_logs.trace_id IS 'OpenTelemetry Trace ID (32-char hex) for correlation with distributed traces';
COMMENT ON COLUMN unifiles.user_activity_logs.span_id IS 'OpenTelemetry Span ID (16-char hex) for exact span correlation';

-- =====================================================
-- 2. 修改 processing_tasks 表
-- =====================================================

-- 添加 trace_id 字段
ALTER TABLE unifiles.processing_tasks
ADD COLUMN IF NOT EXISTS trace_id TEXT;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_processing_tasks_trace_id
ON unifiles.processing_tasks(trace_id)
WHERE trace_id IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN unifiles.processing_tasks.trace_id IS 'OpenTelemetry Trace ID for worker task correlation';

-- =====================================================
-- 3. 辅助查询函数
-- =====================================================

-- 函数: 通过 trace_id 查询所有关联的审计日志
CREATE OR REPLACE FUNCTION unifiles.get_audit_logs_by_trace_id(
    p_trace_id TEXT
)
RETURNS TABLE (
    log_id TEXT,
    user_id TEXT,
    activity_type TEXT,
    activity_details JSONB,
    ip_address INET,
    user_agent TEXT,
    span_id TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        id AS log_id,
        user_id,
        activity_type,
        activity_details,
        ip_address,
        user_agent,
        span_id,
        created_at
    FROM unifiles.user_activity_logs
    WHERE trace_id = p_trace_id
    ORDER BY created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION unifiles.get_audit_logs_by_trace_id IS 'Query all audit logs associated with a specific OpenTelemetry Trace ID';

-- 函数: 通过 trace_id 查询所有关联的任务
CREATE OR REPLACE FUNCTION unifiles.get_tasks_by_trace_id(
    p_trace_id TEXT
)
RETURNS TABLE (
    task_id TEXT,
    task_type TEXT,
    status TEXT,
    user_id TEXT,
    file_id TEXT,
    progress INTEGER,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        id AS task_id,
        task_type,
        status,
        user_id,
        file_id,
        progress,
        created_at,
        updated_at
    FROM unifiles.processing_tasks
    WHERE trace_id = p_trace_id
    ORDER BY created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION unifiles.get_tasks_by_trace_id IS 'Query all processing tasks associated with a specific OpenTelemetry Trace ID';

-- 函数: 获取完整的 Trace 关联信息（审计日志 + 任务）
CREATE OR REPLACE FUNCTION unifiles.get_trace_context(
    p_trace_id TEXT
)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
    audit_logs JSONB;
    tasks JSONB;
BEGIN
    -- 查询审计日志
    SELECT jsonb_agg(row_to_json(t))
    INTO audit_logs
    FROM (
        SELECT * FROM unifiles.get_audit_logs_by_trace_id(p_trace_id)
    ) t;

    -- 查询任务
    SELECT jsonb_agg(row_to_json(t))
    INTO tasks
    FROM (
        SELECT * FROM unifiles.get_tasks_by_trace_id(p_trace_id)
    ) t;

    -- 构建结果
    result := jsonb_build_object(
        'trace_id', p_trace_id,
        'audit_logs', COALESCE(audit_logs, '[]'::jsonb),
        'tasks', COALESCE(tasks, '[]'::jsonb),
        'queried_at', NOW()
    );

    RETURN result;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION unifiles.get_trace_context IS 'Get complete trace context including audit logs and tasks';

-- =====================================================
-- 4. 查询示例
-- =====================================================

-- 示例 1: 通过 trace_id 查询审计日志
-- SELECT * FROM unifiles.get_audit_logs_by_trace_id('0123456789abcdef0123456789abcdef');

-- 示例 2: 通过 trace_id 查询任务
-- SELECT * FROM unifiles.get_tasks_by_trace_id('0123456789abcdef0123456789abcdef');

-- 示例 3: 获取完整的 Trace 上下文
-- SELECT unifiles.get_trace_context('0123456789abcdef0123456789abcdef');

-- 示例 4: 查询特定用户的所有带 Trace ID 的活动
-- SELECT
--     activity_type,
--     trace_id,
--     created_at,
--     activity_details
-- FROM unifiles.user_activity_logs
-- WHERE user_id = 'user_123'
-- AND trace_id IS NOT NULL
-- ORDER BY created_at DESC
-- LIMIT 100;

-- =====================================================
-- 5. 数据统计
-- =====================================================

-- 查看有多少审计日志已关联 Trace ID
-- SELECT
--     COUNT(*) AS total_logs,
--     COUNT(trace_id) AS logs_with_trace_id,
--     ROUND(COUNT(trace_id)::NUMERIC / COUNT(*) * 100, 2) AS trace_coverage_percent
-- FROM unifiles.user_activity_logs;

-- =====================================================
-- 迁移完成
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '027-add-otel-trace-id.sql migration completed successfully';
    RAISE NOTICE 'Added trace_id and span_id columns to user_activity_logs and processing_tasks';
    RAISE NOTICE 'Created helper functions for trace correlation queries';
END $$;
