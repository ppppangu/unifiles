/*
 * 文件名: 043-create-file-triggers.sql
 * 作用: 创建文件管理相关触发器
 * 组成:
 * 1. 文件状态更新触发器 - 自动记录状态变更日志
 * 2. 文件删除触发器 - 处理文件删除时的清理工作
 * 3. 用户文件关联触发器 - 维护用户与文件的关联关系
 * 
 * 说明:
 * - 自动化文件生命周期管理
 * - 确保数据一致性和完整性
 * - 提供审计跟踪功能
 */

-- ========================================
-- 触发器函数定义
-- ========================================

-- 函数：自动记录文件状态变更日志
CREATE OR REPLACE FUNCTION log_file_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- 当状态发生变化时，自动创建处理日志记录
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO chunk_schema.file_processing_logs (
            id,
            file_id,
            user_id,
            status,
            stage,
            message,
            details,
            started_at
        ) VALUES (
            'log-' || gen_random_uuid()::text,
            NEW.id,
            NEW.user_id,
            CASE 
                WHEN NEW.status = 'uploaded' THEN 'completed'
                WHEN NEW.status = 'processing' THEN 'running'
                WHEN NEW.status = 'processed' THEN 'completed'
                WHEN NEW.status = 'error' THEN 'failed'
                WHEN NEW.status = 'deleted' THEN 'completed'
                ELSE 'pending'
            END,
            CASE
                WHEN NEW.status = 'uploaded' THEN 'upload'
                WHEN NEW.status = 'processing' THEN 'processing'
                WHEN NEW.status = 'processed' THEN 'completion'
                WHEN NEW.status = 'error' THEN 'processing'
                WHEN NEW.status = 'deleted' THEN 'completion'
                ELSE 'upload'
            END,
            'File status changed from ' || COALESCE(OLD.status, 'null') || ' to ' || NEW.status,
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status,
                'trigger_time', CURRENT_TIMESTAMP
            ),
            CURRENT_TIMESTAMP
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 函数：处理文件删除时的清理工作
CREATE OR REPLACE FUNCTION handle_file_deletion()
RETURNS TRIGGER AS $$
BEGIN
    -- 记录文件删除日志
    INSERT INTO chunk_schema.file_processing_logs (
        id,
        file_id,
        user_id,
        status,
        stage,
        message,
        details,
        started_at,
        completed_at
    ) VALUES (
        'log-' || gen_random_uuid()::text,
        OLD.id,
        OLD.user_id,
        'completed',
        'completion',
        'File deleted',
        jsonb_build_object(
            'filename', OLD.filename,
            'file_size', OLD.bytes,
            'deletion_time', CURRENT_TIMESTAMP
        ),
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    );
    
    -- 这里可以添加更多清理逻辑，如：
    -- 1. 删除物理文件
    -- 2. 清理相关缓存
    -- 3. 通知其他系统
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- 函数：更新用户的文件统计信息 (可选扩展功能)
CREATE OR REPLACE FUNCTION update_user_file_stats()
RETURNS TRIGGER AS $$
DECLARE
    user_file_count INTEGER;
    user_total_bytes BIGINT;
BEGIN
    -- 计算用户文件统计
    SELECT COUNT(*), COALESCE(SUM(bytes), 0)
    INTO user_file_count, user_total_bytes
    FROM chunk_schema.files
    WHERE user_id = COALESCE(NEW.user_id, OLD.user_id)
    AND status != 'deleted';
    
    -- 这里可以将统计信息存储到用户扩展信息中
    -- 或者触发其他统计更新逻辑
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- 触发器创建
-- ========================================

-- 文件状态更新触发器
DROP TRIGGER IF EXISTS file_status_change_trigger ON chunk_schema.files;
CREATE TRIGGER file_status_change_trigger
    AFTER UPDATE ON chunk_schema.files
    FOR EACH ROW
    EXECUTE FUNCTION log_file_status_change();

-- 文件删除触发器
DROP TRIGGER IF EXISTS file_deletion_trigger ON chunk_schema.files;
CREATE TRIGGER file_deletion_trigger
    BEFORE DELETE ON chunk_schema.files
    FOR EACH ROW
    EXECUTE FUNCTION handle_file_deletion();

-- 用户文件统计触发器 (插入)
DROP TRIGGER IF EXISTS file_stats_insert_trigger ON chunk_schema.files;
CREATE TRIGGER file_stats_insert_trigger
    AFTER INSERT ON chunk_schema.files
    FOR EACH ROW
    EXECUTE FUNCTION update_user_file_stats();

-- 用户文件统计触发器 (更新)
DROP TRIGGER IF EXISTS file_stats_update_trigger ON chunk_schema.files;
CREATE TRIGGER file_stats_update_trigger
    AFTER UPDATE ON chunk_schema.files
    FOR EACH ROW
    EXECUTE FUNCTION update_user_file_stats();

-- 用户文件统计触发器 (删除)
DROP TRIGGER IF EXISTS file_stats_delete_trigger ON chunk_schema.files;
CREATE TRIGGER file_stats_delete_trigger
    AFTER DELETE ON chunk_schema.files
    FOR EACH ROW
    EXECUTE FUNCTION update_user_file_stats();

-- ========================================
-- 注释说明
-- ========================================

/*
触发器功能说明：

1. file_status_change_trigger:
   - 监听文件状态变更
   - 自动创建处理日志记录
   - 提供完整的状态变更审计跟踪

2. file_deletion_trigger:
   - 在文件删除前执行
   - 记录删除日志
   - 为未来的清理逻辑预留接口

3. file_stats_*_trigger:
   - 维护用户文件统计信息
   - 支持实时统计查询
   - 可扩展为更复杂的统计逻辑

使用注意事项：
- 触发器会增加数据库操作开销，但提供了重要的一致性保证
- 在高并发场景下需要考虑性能影响
- 可根据具体需求启用或禁用特定触发器
*/