/*
 * 文件名: 042-create-file-indexes.sql
 * 作用: 为文件管理表创建索引
 * 组成:
 * 1. files表索引 - 提高文件查询性能
 * 2. file_processing_logs表索引 - 提高日志查询性能
 * 3. 复合索引 - 优化常见查询组合
 * 
 * 说明:
 * - 用户文件查询是最常见的操作，需要优化
 * - 状态查询用于文件管理和监控
 * - 时间索引支持按时间排序和范围查询
 */

-- ========================================
-- 文件表索引
-- ========================================

-- 用户文件查询索引 (最常用)
CREATE INDEX IF NOT EXISTS idx_files_user_id 
    ON chunk_schema.files(user_id);

-- 文件状态查询索引 (用于监控和管理)
CREATE INDEX IF NOT EXISTS idx_files_status 
    ON chunk_schema.files(status);

-- 文件创建时间索引 (支持时间排序)
CREATE INDEX IF NOT EXISTS idx_files_created_at 
    ON chunk_schema.files(created_at DESC);

-- 文件用途索引 (按用途筛选)
CREATE INDEX IF NOT EXISTS idx_files_purpose 
    ON chunk_schema.files(purpose);

-- 用户文件状态复合索引 (优化常见查询组合)
CREATE INDEX IF NOT EXISTS idx_files_user_status 
    ON chunk_schema.files(user_id, status);

-- 用户文件用途复合索引 (按用户和用途查询)
CREATE INDEX IF NOT EXISTS idx_files_user_purpose 
    ON chunk_schema.files(user_id, purpose);

-- 用户文件创建时间复合索引 (用户文件时间排序)
CREATE INDEX IF NOT EXISTS idx_files_user_created 
    ON chunk_schema.files(user_id, created_at DESC);

-- ========================================
-- 文件处理日志表索引
-- ========================================

-- 文件处理日志关联索引 (查询特定文件的处理记录)
CREATE INDEX IF NOT EXISTS idx_processing_logs_file_id 
    ON chunk_schema.file_processing_logs(file_id);

-- 用户处理日志索引 (查询用户的处理记录)
CREATE INDEX IF NOT EXISTS idx_processing_logs_user_id 
    ON chunk_schema.file_processing_logs(user_id);

-- 处理日志时间索引 (按时间排序查询)
CREATE INDEX IF NOT EXISTS idx_processing_logs_started_at 
    ON chunk_schema.file_processing_logs(started_at DESC);

-- 处理状态索引 (查询特定状态的记录)
CREATE INDEX IF NOT EXISTS idx_processing_logs_status 
    ON chunk_schema.file_processing_logs(status);

-- 处理阶段索引 (查询特定阶段的记录)
CREATE INDEX IF NOT EXISTS idx_processing_logs_stage 
    ON chunk_schema.file_processing_logs(stage);

-- 文件处理状态复合索引 (查询文件的特定状态记录)
CREATE INDEX IF NOT EXISTS idx_processing_logs_file_status 
    ON chunk_schema.file_processing_logs(file_id, status);

-- 用户文件处理时间复合索引 (用户处理记录按时间排序)
CREATE INDEX IF NOT EXISTS idx_processing_logs_user_started 
    ON chunk_schema.file_processing_logs(user_id, started_at DESC);