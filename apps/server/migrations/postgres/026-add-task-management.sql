-- =====================================================
-- Unifiles Task Management System
-- 任务管理系统数据库表和函数
--
-- 功能：
-- 1. 异步任务记录和追踪
-- 2. 任务状态管理
-- 3. 任务执行日志
-- 4. 任务查询和统计
--
-- 版本: 1.0.0
-- 创建日期: 2025-10-16
-- =====================================================

-- ========================================
-- 1. 任务记录表
-- ========================================

CREATE TABLE IF NOT EXISTS unifiles.processing_tasks (
    -- 主键和标识
    id TEXT PRIMARY KEY DEFAULT ('task_' || encode(gen_random_bytes(16), 'hex')),

    -- 任务基本信息
    task_type TEXT NOT NULL,                    -- 任务类型：file_upload, file_process_ocr, webhook_dispatch 等
    status TEXT NOT NULL DEFAULT 'queued',      -- 任务状态：queued, processing, completed, failed, cancelled, retry
    priority INTEGER DEFAULT 0,                 -- 优先级：0=低, 10=普通, 50=高, 100=紧急

    -- 关联信息
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,
    file_id TEXT REFERENCES unifiles.files(id) ON DELETE CASCADE,  -- 文件相关任务
    related_task_id TEXT REFERENCES unifiles.processing_tasks(id) ON DELETE SET NULL,  -- 关联的父任务

    -- 任务数据
    task_data JSONB DEFAULT '{}',               -- 任务输入数据
    result_data JSONB DEFAULT '{}',             -- 任务执行结果
    error_data JSONB DEFAULT '{}',              -- 错误信息

    -- 进度信息
    progress INTEGER DEFAULT 0,                 -- 进度百分比 (0-100)
    progress_message TEXT,                      -- 进度描述信息

    -- 重试控制
    retry_count INTEGER DEFAULT 0,              -- 当前重试次数
    max_retries INTEGER DEFAULT 3,              -- 最大重试次数

    -- 时间信息
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    queued_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,                     -- 开始处理时间
    completed_at TIMESTAMPTZ,                   -- 完成时间
    failed_at TIMESTAMPTZ,                      -- 失败时间

    -- 性能追踪
    execution_time_ms INTEGER,                  -- 执行时间（毫秒）
    worker_id TEXT,                             -- 处理该任务的 Worker ID

    -- 元数据
    metadata JSONB DEFAULT '{}',                -- 额外的元数据

    -- 约束
    CONSTRAINT chk_task_status
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled', 'retry')),
    CONSTRAINT chk_progress_range
        CHECK (progress >= 0 AND progress <= 100),
    CONSTRAINT chk_priority_range
        CHECK (priority >= 0 AND priority <= 100)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_processing_tasks_user_id ON unifiles.processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_status ON unifiles.processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_file_id ON unifiles.processing_tasks(file_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_task_type ON unifiles.processing_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_created_at ON unifiles.processing_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_user_status ON unifiles.processing_tasks(user_id, status);

-- 组合索引：用户+状态+创建时间（常用查询）
CREATE INDEX IF NOT EXISTS idx_processing_tasks_user_status_created
    ON unifiles.processing_tasks(user_id, status, created_at DESC);

-- JSONB 索引（用于复杂查询）
CREATE INDEX IF NOT EXISTS idx_processing_tasks_task_data_gin
    ON unifiles.processing_tasks USING GIN (task_data);

COMMENT ON TABLE unifiles.processing_tasks IS '异步任务记录表 - 存储所有异步处理任务的状态和结果';
COMMENT ON COLUMN unifiles.processing_tasks.task_type IS '任务类型：file_upload, file_process_ocr, file_process_ai_extraction, webhook_dispatch 等';
COMMENT ON COLUMN unifiles.processing_tasks.status IS '任务状态：queued=已入队, processing=处理中, completed=已完成, failed=失败, cancelled=已取消, retry=重试中';
COMMENT ON COLUMN unifiles.processing_tasks.priority IS '优先级：0=低优先级, 10=普通, 50=高优先级(付费用户), 100=紧急(VIP)';


-- ========================================
-- 2. 任务执行日志表
-- ========================================

CREATE TABLE IF NOT EXISTS unifiles.task_logs (
    -- 主键
    id TEXT PRIMARY KEY DEFAULT ('tasklog_' || encode(gen_random_bytes(16), 'hex')),

    -- 关联任务
    task_id TEXT NOT NULL REFERENCES unifiles.processing_tasks(id) ON DELETE CASCADE,

    -- 日志信息
    log_level TEXT NOT NULL DEFAULT 'info',     -- 日志级别：debug, info, warning, error
    log_message TEXT NOT NULL,                  -- 日志消息
    log_data JSONB DEFAULT '{}',                -- 额外的日志数据

    -- Worker 信息
    worker_id TEXT,                             -- 产生日志的 Worker ID
    worker_type TEXT,                           -- Worker 类型

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_log_level
        CHECK (log_level IN ('debug', 'info', 'warning', 'error'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON unifiles.task_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_created_at ON unifiles.task_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_logs_log_level ON unifiles.task_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_task_logs_task_created ON unifiles.task_logs(task_id, created_at DESC);

COMMENT ON TABLE unifiles.task_logs IS '任务执行日志表 - 记录任务处理过程中的所有日志';


-- ========================================
-- 3. 创建任务函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.create_processing_task(
    p_user_id TEXT,
    p_task_type TEXT,
    p_task_data JSONB DEFAULT '{}',
    p_file_id TEXT DEFAULT NULL,
    p_priority INTEGER DEFAULT 10,
    p_related_task_id TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
) RETURNS JSONB AS $$
DECLARE
    v_task_id TEXT;
    v_result JSONB;
BEGIN
    -- 插入任务记录
    INSERT INTO unifiles.processing_tasks (
        user_id,
        task_type,
        task_data,
        file_id,
        priority,
        related_task_id,
        metadata,
        status,
        queued_at
    ) VALUES (
        p_user_id,
        p_task_type,
        p_task_data,
        p_file_id,
        p_priority,
        p_related_task_id,
        p_metadata,
        'queued',
        CURRENT_TIMESTAMP
    )
    RETURNING id INTO v_task_id;

    -- 记录审计日志
    INSERT INTO unifiles.user_activity_logs (
        user_id,
        action_type,
        resource_type,
        resource_id,
        action_metadata
    ) VALUES (
        p_user_id,
        'task_created',
        'processing_task',
        v_task_id,
        jsonb_build_object(
            'task_type', p_task_type,
            'priority', p_priority
        )
    );

    -- 返回结果
    v_result := jsonb_build_object(
        'success', true,
        'task_id', v_task_id,
        'status', 'queued',
        'message', 'Task created successfully'
    );

    RETURN v_result;

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'message', 'Failed to create task'
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.create_processing_task IS '创建异步处理任务';


-- ========================================
-- 4. 更新任务状态函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.update_task_status(
    p_task_id TEXT,
    p_status TEXT,
    p_progress INTEGER DEFAULT NULL,
    p_progress_message TEXT DEFAULT NULL,
    p_result_data JSONB DEFAULT NULL,
    p_error_data JSONB DEFAULT NULL,
    p_worker_id TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_old_status TEXT;
    v_execution_time_ms INTEGER;
    v_user_id TEXT;
BEGIN
    -- 获取旧状态和用户 ID
    SELECT status, user_id INTO v_old_status, v_user_id
    FROM unifiles.processing_tasks
    WHERE id = p_task_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'task_not_found',
            'message', 'Task not found'
        );
    END IF;

    -- 计算执行时间
    IF p_status IN ('completed', 'failed') THEN
        SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000 INTO v_execution_time_ms
        FROM unifiles.processing_tasks
        WHERE id = p_task_id;
    END IF;

    -- 更新任务状态
    UPDATE unifiles.processing_tasks
    SET
        status = p_status,
        progress = COALESCE(p_progress, progress),
        progress_message = COALESCE(p_progress_message, progress_message),
        result_data = COALESCE(p_result_data, result_data),
        error_data = COALESCE(p_error_data, error_data),
        worker_id = COALESCE(p_worker_id, worker_id),
        execution_time_ms = COALESCE(v_execution_time_ms, execution_time_ms),
        started_at = CASE
            WHEN p_status = 'processing' AND started_at IS NULL
            THEN CURRENT_TIMESTAMP
            ELSE started_at
        END,
        completed_at = CASE
            WHEN p_status = 'completed'
            THEN CURRENT_TIMESTAMP
            ELSE completed_at
        END,
        failed_at = CASE
            WHEN p_status = 'failed'
            THEN CURRENT_TIMESTAMP
            ELSE failed_at
        END
    WHERE id = p_task_id;

    -- 记录状态变更日志
    IF v_old_status != p_status THEN
        INSERT INTO unifiles.task_logs (
            task_id,
            log_level,
            log_message,
            worker_id
        ) VALUES (
            p_task_id,
            CASE
                WHEN p_status = 'failed' THEN 'error'
                WHEN p_status = 'completed' THEN 'info'
                ELSE 'info'
            END,
            format('Task status changed from %s to %s', v_old_status, p_status),
            p_worker_id
        );

        -- 记录审计日志
        INSERT INTO unifiles.user_activity_logs (
            user_id,
            action_type,
            resource_type,
            resource_id,
            action_metadata
        ) VALUES (
            v_user_id,
            'task_status_changed',
            'processing_task',
            p_task_id,
            jsonb_build_object(
                'old_status', v_old_status,
                'new_status', p_status,
                'progress', p_progress
            )
        );
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'task_id', p_task_id,
        'old_status', v_old_status,
        'new_status', p_status,
        'message', 'Task status updated successfully'
    );

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'message', 'Failed to update task status'
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.update_task_status IS '更新任务状态和进度';


-- ========================================
-- 5. 获取任务详情函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.get_task_by_id(
    p_task_id TEXT,
    p_user_id TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    v_task RECORD;
    v_result JSONB;
BEGIN
    -- 查询任务
    SELECT * INTO v_task
    FROM unifiles.processing_tasks
    WHERE id = p_task_id
      AND (p_user_id IS NULL OR user_id = p_user_id);

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'task_not_found',
            'message', 'Task not found or access denied'
        );
    END IF;

    -- 构建返回结果
    v_result := jsonb_build_object(
        'success', true,
        'task', jsonb_build_object(
            'id', v_task.id,
            'task_type', v_task.task_type,
            'status', v_task.status,
            'priority', v_task.priority,
            'user_id', v_task.user_id,
            'file_id', v_task.file_id,
            'related_task_id', v_task.related_task_id,
            'task_data', v_task.task_data,
            'result_data', v_task.result_data,
            'error_data', v_task.error_data,
            'progress', v_task.progress,
            'progress_message', v_task.progress_message,
            'retry_count', v_task.retry_count,
            'max_retries', v_task.max_retries,
            'created_at', v_task.created_at,
            'queued_at', v_task.queued_at,
            'started_at', v_task.started_at,
            'completed_at', v_task.completed_at,
            'failed_at', v_task.failed_at,
            'execution_time_ms', v_task.execution_time_ms,
            'worker_id', v_task.worker_id,
            'metadata', v_task.metadata
        )
    );

    RETURN v_result;

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'message', 'Failed to get task'
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.get_task_by_id IS '根据 ID 获取任务详情';


-- ========================================
-- 6. 获取用户任务列表函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.get_user_tasks(
    p_user_id TEXT,
    p_status TEXT DEFAULT NULL,
    p_task_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
) RETURNS JSONB AS $$
DECLARE
    v_tasks JSONB;
    v_total_count INTEGER;
BEGIN
    -- 获取任务列表
    SELECT jsonb_agg(
        jsonb_build_object(
            'id', t.id,
            'task_type', t.task_type,
            'status', t.status,
            'priority', t.priority,
            'file_id', t.file_id,
            'progress', t.progress,
            'progress_message', t.progress_message,
            'retry_count', t.retry_count,
            'created_at', t.created_at,
            'started_at', t.started_at,
            'completed_at', t.completed_at,
            'execution_time_ms', t.execution_time_ms
        )
    ) INTO v_tasks
    FROM (
        SELECT *
        FROM unifiles.processing_tasks
        WHERE user_id = p_user_id
          AND (p_status IS NULL OR status = p_status)
          AND (p_task_type IS NULL OR task_type = p_task_type)
        ORDER BY created_at DESC
        LIMIT p_limit
        OFFSET p_offset
    ) t;

    -- 获取总数
    SELECT COUNT(*) INTO v_total_count
    FROM unifiles.processing_tasks
    WHERE user_id = p_user_id
      AND (p_status IS NULL OR status = p_status)
      AND (p_task_type IS NULL OR task_type = p_task_type);

    RETURN jsonb_build_object(
        'success', true,
        'tasks', COALESCE(v_tasks, '[]'::jsonb),
        'total_count', v_total_count,
        'limit', p_limit,
        'offset', p_offset
    );

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'message', 'Failed to get user tasks'
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.get_user_tasks IS '获取用户的任务列表（支持过滤和分页）';


-- ========================================
-- 7. 清理旧任务函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.cleanup_old_tasks(
    p_days_to_keep INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- 删除已完成或失败的旧任务
    WITH deleted AS (
        DELETE FROM unifiles.processing_tasks
        WHERE status IN ('completed', 'failed', 'cancelled')
          AND created_at < CURRENT_TIMESTAMP - (p_days_to_keep || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO v_deleted_count FROM deleted;

    -- 记录清理日志
    IF v_deleted_count > 0 THEN
        RAISE NOTICE 'Cleaned up % old tasks older than % days', v_deleted_count, p_days_to_keep;
    END IF;

    RETURN v_deleted_count;

EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Error cleaning up old tasks: %', SQLERRM;
        RETURN 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.cleanup_old_tasks IS '清理超过指定天数的已完成或失败任务（默认 30 天）';


-- ========================================
-- 8. 任务统计函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.get_task_statistics(
    p_user_id TEXT DEFAULT NULL,
    p_since TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP - INTERVAL '7 days'
) RETURNS JSONB AS $$
DECLARE
    v_stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_tasks', COUNT(*),
        'queued_tasks', COUNT(*) FILTER (WHERE status = 'queued'),
        'processing_tasks', COUNT(*) FILTER (WHERE status = 'processing'),
        'completed_tasks', COUNT(*) FILTER (WHERE status = 'completed'),
        'failed_tasks', COUNT(*) FILTER (WHERE status = 'failed'),
        'cancelled_tasks', COUNT(*) FILTER (WHERE status = 'cancelled'),
        'avg_execution_time_ms', AVG(execution_time_ms) FILTER (WHERE execution_time_ms IS NOT NULL),
        'max_execution_time_ms', MAX(execution_time_ms),
        'min_execution_time_ms', MIN(execution_time_ms) FILTER (WHERE execution_time_ms IS NOT NULL),
        'success_rate', ROUND(
            COUNT(*) FILTER (WHERE status = 'completed')::DECIMAL /
            NULLIF(COUNT(*) FILTER (WHERE status IN ('completed', 'failed')), 0) * 100,
            2
        ),
        'by_type', (
            SELECT jsonb_object_agg(
                task_type,
                COUNT(*)
            )
            FROM unifiles.processing_tasks
            WHERE (p_user_id IS NULL OR user_id = p_user_id)
              AND created_at >= p_since
            GROUP BY task_type
        )
    ) INTO v_stats
    FROM unifiles.processing_tasks
    WHERE (p_user_id IS NULL OR user_id = p_user_id)
      AND created_at >= p_since;

    RETURN v_stats;

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.get_task_statistics IS '获取任务统计信息（可按用户和时间过滤）';


-- ========================================
-- 9. 任务重试函数
-- ========================================

CREATE OR REPLACE FUNCTION unifiles.retry_failed_task(
    p_task_id TEXT
) RETURNS JSONB AS $$
DECLARE
    v_task RECORD;
BEGIN
    -- 获取任务信息
    SELECT * INTO v_task
    FROM unifiles.processing_tasks
    WHERE id = p_task_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'task_not_found',
            'message', 'Task not found'
        );
    END IF;

    -- 检查是否可以重试
    IF v_task.status NOT IN ('failed', 'cancelled') THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'invalid_status',
            'message', 'Only failed or cancelled tasks can be retried'
        );
    END IF;

    IF v_task.retry_count >= v_task.max_retries THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'max_retries_exceeded',
            'message', 'Maximum retry count exceeded'
        );
    END IF;

    -- 更新任务状态为 retry
    UPDATE unifiles.processing_tasks
    SET
        status = 'retry',
        retry_count = retry_count + 1,
        queued_at = CURRENT_TIMESTAMP,
        failed_at = NULL,
        error_data = '{}'
    WHERE id = p_task_id;

    -- 记录日志
    INSERT INTO unifiles.task_logs (
        task_id,
        log_level,
        log_message
    ) VALUES (
        p_task_id,
        'info',
        format('Task retry initiated (attempt %s/%s)', v_task.retry_count + 1, v_task.max_retries)
    );

    RETURN jsonb_build_object(
        'success', true,
        'task_id', p_task_id,
        'retry_count', v_task.retry_count + 1,
        'message', 'Task queued for retry'
    );

EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM,
            'message', 'Failed to retry task'
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION unifiles.retry_failed_task IS '重试失败的任务';


-- ========================================
-- 10. 授权和权限
-- ========================================

-- 授权给 API 用户
GRANT SELECT, INSERT, UPDATE, DELETE ON unifiles.processing_tasks TO unifiles_api;
GRANT SELECT, INSERT ON unifiles.task_logs TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.create_processing_task TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.update_task_status TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.get_task_by_id TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.get_user_tasks TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.cleanup_old_tasks TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.get_task_statistics TO unifiles_api;
GRANT EXECUTE ON FUNCTION unifiles.retry_failed_task TO unifiles_api;


-- ========================================
-- 完成
-- ========================================

-- 显示总结信息
DO $$
BEGIN
    RAISE NOTICE '=========================================';
    RAISE NOTICE 'Task Management System Installation Complete';
    RAISE NOTICE '=========================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - unifiles.processing_tasks';
    RAISE NOTICE '  - unifiles.task_logs';
    RAISE NOTICE '';
    RAISE NOTICE 'Functions created:';
    RAISE NOTICE '  - create_processing_task()';
    RAISE NOTICE '  - update_task_status()';
    RAISE NOTICE '  - get_task_by_id()';
    RAISE NOTICE '  - get_user_tasks()';
    RAISE NOTICE '  - cleanup_old_tasks()';
    RAISE NOTICE '  - get_task_statistics()';
    RAISE NOTICE '  - retry_failed_task()';
    RAISE NOTICE '';
    RAISE NOTICE 'Ready for async task processing!';
    RAISE NOTICE '=========================================';
END $$;
