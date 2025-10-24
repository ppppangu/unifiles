/*
 * 文件名: 042-create-async-tasks.sql
 * 作用: 创建异步任务管理表
 * 分类: 任务管理层
 * 执行顺序: 第四步补充 - 在内容提取层创建后执行
 *
 * 设计说明:
 * 1. async_tasks表: 统一管理所有异步任务（提取、分块、嵌入等）
 * 2. 支持任务状态追踪、进度反馈、重试机制
 * 3. 与业务表（extracted_documents等）解耦，通过entity_id关联
 * 4. 支持后台任务（FastAPI BackgroundTasks）和分布式任务（Celery）
 */

-- ================================
-- 异步任务表 (Async Tasks)
-- ================================

CREATE TABLE IF NOT EXISTS unifiles.async_tasks (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 任务ID（UUID）

    -- 任务分类
    task_type TEXT NOT NULL,                               -- 任务类型（extraction, chunking, embedding, indexing）
    task_category TEXT DEFAULT 'processing',               -- 任务类别（processing, maintenance, migration）

    -- 关联实体
    entity_type TEXT,                                      -- 实体类型（extracted_document, document, knowledge_base）
    entity_id TEXT,                                        -- 实体ID（如extraction_id, document_id）

    -- 任务状态
    status TEXT NOT NULL DEFAULT 'pending',                -- 任务状态
    progress_percent INTEGER DEFAULT 0,                    -- 进度百分比（0-100）
    progress_message TEXT,                                 -- 当前阶段描述

    -- 任务参数和结果
    input_params JSONB DEFAULT '{}',                       -- 输入参数
    /*
     * input_params 示例（提取任务）:
     * {
     *   "file_id": "abc123",
     *   "mode": "mistral",
     *   "user_preferences": {...}
     * }
     */

    result_data JSONB DEFAULT '{}',                        -- 任务结果
    /*
     * result_data 示例:
     * {
     *   "extraction_id": "def456",
     *   "total_pages": 10,
     *   "markdown_length": 5000
     * }
     */

    -- 错误信息
    error_message TEXT,                                    -- 错误消息
    error_code TEXT,                                       -- 错误代码
    error_details JSONB DEFAULT '{}',                      -- 错误详情
    stack_trace TEXT,                                      -- 堆栈跟踪

    -- 用户信息
    user_id TEXT NOT NULL,                                 -- 发起用户

    -- 时间信息
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 任务创建时间
    queued_at TIMESTAMPTZ,                                 -- 任务入队时间
    started_at TIMESTAMPTZ,                                -- 任务开始时间
    completed_at TIMESTAMPTZ,                              -- 任务完成时间

    -- 重试机制
    retry_count INTEGER DEFAULT 0,                         -- 已重试次数
    max_retries INTEGER DEFAULT 3,                         -- 最大重试次数
    last_retry_at TIMESTAMPTZ,                             -- 最后重试时间
    retry_reason TEXT,                                     -- 重试原因

    -- 优先级和调度
    priority INTEGER DEFAULT 5,                            -- 任务优先级（1-10，数字越小优先级越高）
    scheduled_at TIMESTAMPTZ,                              -- 计划执行时间
    timeout_seconds INTEGER DEFAULT 600,                   -- 超时时间（秒）

    -- 任务元数据
    worker_id TEXT,                                        -- 执行该任务的Worker ID（用于分布式）
    celery_task_id TEXT,                                   -- Celery任务ID（如果使用Celery）
    execution_context JSONB DEFAULT '{}',                  -- 执行上下文
    /*
     * execution_context 示例:
     * {
     *   "worker_host": "worker-01",
     *   "worker_version": "1.0.0",
     *   "execution_env": "production"
     * }
     */

    -- 过期和清理
    expires_at TIMESTAMPTZ,                                -- 任务结果过期时间
    is_archived BOOLEAN DEFAULT FALSE,                     -- 是否已归档

    -- 外键约束
    CONSTRAINT fk_async_tasks_user_id
        FOREIGN KEY (user_id) REFERENCES unifiles.users(id) ON DELETE CASCADE,

    -- 检查约束
    CONSTRAINT chk_async_tasks_type
        CHECK (task_type IN ('extraction', 'chunking', 'embedding', 'indexing',
                            'fine_tuning', 'migration', 'cleanup', 'export', 'custom')),
    CONSTRAINT chk_async_tasks_status
        CHECK (status IN ('pending', 'queued', 'processing', 'completed',
                         'failed', 'cancelled', 'interrupted', 'timeout')),
    CONSTRAINT chk_async_tasks_progress
        CHECK (progress_percent >= 0 AND progress_percent <= 100),
    CONSTRAINT chk_async_tasks_priority
        CHECK (priority >= 1 AND priority <= 10),
    CONSTRAINT chk_async_tasks_retry_count
        CHECK (retry_count >= 0 AND retry_count <= max_retries),
    CONSTRAINT chk_async_tasks_entity_type
        CHECK (entity_type IN ('file', 'extracted_document', 'document', 'asset',
                              'chunk', 'knowledge_base', 'batch', 'pipeline'))
);

-- ================================
-- 任务依赖表 (Task Dependencies)
-- ================================

-- 用于定义任务间的依赖关系（高级功能，可选）
CREATE TABLE IF NOT EXISTS unifiles.task_dependencies (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,                                 -- 当前任务ID
    depends_on_task_id TEXT NOT NULL,                      -- 依赖的任务ID
    dependency_type TEXT DEFAULT 'completion',             -- 依赖类型（completion, partial, conditional）
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_task_dependencies_task_id
        FOREIGN KEY (task_id) REFERENCES unifiles.async_tasks(id) ON DELETE CASCADE,
    CONSTRAINT fk_task_dependencies_depends_on
        FOREIGN KEY (depends_on_task_id) REFERENCES unifiles.async_tasks(id) ON DELETE CASCADE,
    CONSTRAINT chk_task_dependencies_type
        CHECK (dependency_type IN ('completion', 'partial', 'conditional')),

    -- 防止循环依赖
    CONSTRAINT chk_task_dependencies_no_self_reference
        CHECK (task_id != depends_on_task_id)
);

-- ================================
-- 索引优化
-- ================================

-- async_tasks表索引
CREATE INDEX idx_async_tasks_user_id
    ON unifiles.async_tasks(user_id);

CREATE INDEX idx_async_tasks_status
    ON unifiles.async_tasks(status)
    WHERE status NOT IN ('completed', 'failed', 'cancelled');

CREATE INDEX idx_async_tasks_type_status
    ON unifiles.async_tasks(task_type, status);

CREATE INDEX idx_async_tasks_entity
    ON unifiles.async_tasks(entity_type, entity_id);

CREATE INDEX idx_async_tasks_created_at
    ON unifiles.async_tasks(created_at DESC);

CREATE INDEX idx_async_tasks_priority_status
    ON unifiles.async_tasks(priority ASC, created_at ASC)
    WHERE status = 'pending';

CREATE INDEX idx_async_tasks_celery
    ON unifiles.async_tasks(celery_task_id)
    WHERE celery_task_id IS NOT NULL;

CREATE INDEX idx_async_tasks_expires
    ON unifiles.async_tasks(expires_at)
    WHERE expires_at IS NOT NULL;

-- 用于清理归档任务
CREATE INDEX idx_async_tasks_archived
    ON unifiles.async_tasks(is_archived, completed_at)
    WHERE is_archived = FALSE;

-- task_dependencies表索引
CREATE INDEX idx_task_dependencies_task_id
    ON unifiles.task_dependencies(task_id);

CREATE INDEX idx_task_dependencies_depends_on
    ON unifiles.task_dependencies(depends_on_task_id);

-- ================================
-- 触发器函数
-- ================================

-- 自动设置任务入队时间
CREATE OR REPLACE FUNCTION unifiles.set_task_queued_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'queued' AND OLD.status != 'queued' THEN
        NEW.queued_at = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_task_queued_time
    BEFORE UPDATE ON unifiles.async_tasks
    FOR EACH ROW
    WHEN (NEW.status = 'queued')
    EXECUTE FUNCTION unifiles.set_task_queued_time();

-- 自动设置任务开始时间
CREATE OR REPLACE FUNCTION unifiles.set_task_started_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'processing' AND OLD.status != 'processing' THEN
        NEW.started_at = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_task_started_time
    BEFORE UPDATE ON unifiles.async_tasks
    FOR EACH ROW
    WHEN (NEW.status = 'processing')
    EXECUTE FUNCTION unifiles.set_task_started_time();

-- 自动设置任务完成时间
CREATE OR REPLACE FUNCTION unifiles.set_task_completed_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('completed', 'failed', 'cancelled', 'timeout')
       AND OLD.status NOT IN ('completed', 'failed', 'cancelled', 'timeout') THEN
        NEW.completed_at = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_task_completed_time
    BEFORE UPDATE ON unifiles.async_tasks
    FOR EACH ROW
    WHEN (NEW.status IN ('completed', 'failed', 'cancelled', 'timeout'))
    EXECUTE FUNCTION unifiles.set_task_completed_time();

-- ================================
-- 辅助函数
-- ================================

-- 获取用户的待处理任务数
CREATE OR REPLACE FUNCTION unifiles.get_user_pending_tasks_count(p_user_id TEXT)
RETURNS INTEGER AS $$
    SELECT COUNT(*)::INTEGER
    FROM unifiles.async_tasks
    WHERE user_id = p_user_id
    AND status IN ('pending', 'queued', 'processing');
$$ LANGUAGE SQL;

-- 获取任务执行时长（秒）
CREATE OR REPLACE FUNCTION unifiles.get_task_duration_seconds(p_task_id TEXT)
RETURNS INTEGER AS $$
    SELECT EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER
    FROM unifiles.async_tasks
    WHERE id = p_task_id
    AND started_at IS NOT NULL
    AND completed_at IS NOT NULL;
$$ LANGUAGE SQL;

-- 清理过期任务
CREATE OR REPLACE FUNCTION unifiles.cleanup_expired_tasks()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM unifiles.async_tasks
        WHERE expires_at < CURRENT_TIMESTAMP
        AND status IN ('completed', 'failed', 'cancelled')
        RETURNING id
    )
    SELECT COUNT(*)::INTEGER INTO deleted_count FROM deleted;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 获取任务统计信息
CREATE OR REPLACE FUNCTION unifiles.get_task_statistics(
    p_user_id TEXT DEFAULT NULL,
    p_start_date TIMESTAMPTZ DEFAULT CURRENT_DATE - INTERVAL '7 days',
    p_end_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
RETURNS TABLE (
    task_type TEXT,
    total_count BIGINT,
    completed_count BIGINT,
    failed_count BIGINT,
    avg_duration_seconds NUMERIC,
    success_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        at.task_type,
        COUNT(*) as total_count,
        COUNT(*) FILTER (WHERE at.status = 'completed') as completed_count,
        COUNT(*) FILTER (WHERE at.status = 'failed') as failed_count,
        ROUND(AVG(
            EXTRACT(EPOCH FROM (at.completed_at - at.started_at))
        ), 2) as avg_duration_seconds,
        ROUND(
            COUNT(*) FILTER (WHERE at.status = 'completed')::NUMERIC /
            NULLIF(COUNT(*), 0) * 100,
            2
        ) as success_rate
    FROM unifiles.async_tasks at
    WHERE at.created_at BETWEEN p_start_date AND p_end_date
    AND (p_user_id IS NULL OR at.user_id = p_user_id)
    GROUP BY at.task_type
    ORDER BY total_count DESC;
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 视图
-- ================================

-- 活跃任务视图（用于监控）
CREATE OR REPLACE VIEW unifiles.active_tasks AS
SELECT
    id,
    task_type,
    status,
    progress_percent,
    progress_message,
    user_id,
    entity_type,
    entity_id,
    priority,
    created_at,
    started_at,
    CASE
        WHEN started_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))::INTEGER
        ELSE NULL
    END as running_seconds
FROM unifiles.async_tasks
WHERE status IN ('pending', 'queued', 'processing')
ORDER BY priority ASC, created_at ASC;

-- 最近失败的任务视图（用于监控和报警）
CREATE OR REPLACE VIEW unifiles.recent_failed_tasks AS
SELECT
    id,
    task_type,
    error_message,
    error_code,
    retry_count,
    max_retries,
    user_id,
    entity_id,
    created_at,
    completed_at
FROM unifiles.async_tasks
WHERE status = 'failed'
AND completed_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY completed_at DESC;

-- ================================
-- 注释说明
-- ================================

COMMENT ON TABLE unifiles.async_tasks IS '异步任务表，统一管理所有后台任务';
COMMENT ON COLUMN unifiles.async_tasks.progress_percent IS '任务进度百分比（0-100），用于前端进度条展示';
COMMENT ON COLUMN unifiles.async_tasks.priority IS '任务优先级（1-10），数字越小优先级越高';
COMMENT ON COLUMN unifiles.async_tasks.celery_task_id IS 'Celery任务ID，仅在使用Celery时填充';
COMMENT ON COLUMN unifiles.async_tasks.entity_id IS '关联的业务实体ID，如extraction_id或document_id';
COMMENT ON COLUMN unifiles.async_tasks.expires_at IS '任务结果过期时间，用于定期清理已完成任务';

COMMENT ON TABLE unifiles.task_dependencies IS '任务依赖表，用于定义任务执行的先后顺序';

COMMENT ON FUNCTION unifiles.get_task_statistics IS '获取任务统计信息，支持按用户和时间范围过滤';
COMMENT ON FUNCTION unifiles.cleanup_expired_tasks IS '清理过期的已完成任务，建议定期执行';
