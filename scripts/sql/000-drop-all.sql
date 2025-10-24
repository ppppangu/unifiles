/*
 * 文件名: 000-drop-all.sql
 * 作用: 删除所有表、视图、函数、触发器，完全重置数据库
 * 警告: 仅在开发环境使用！此操作会删除所有数据！
 */

-- ================================
-- 删除所有表（按依赖关系逆序删除）
-- ================================

-- 组件层
DROP TABLE IF EXISTS unifiles.photos CASCADE;
DROP TABLE IF EXISTS unifiles.chunks CASCADE;
DROP TABLE IF EXISTS unifiles.components CASCADE;

-- 知识库层
DROP TABLE IF EXISTS unifiles.kb_statistics CASCADE;
DROP TABLE IF EXISTS unifiles.documents CASCADE;
DROP TABLE IF EXISTS unifiles.knowledge_bases CASCADE;

-- 异步任务层
DROP TABLE IF EXISTS unifiles.task_dependencies CASCADE;
DROP TABLE IF EXISTS unifiles.async_tasks CASCADE;

-- 内容提取层
DROP TABLE IF EXISTS unifiles.process_logs CASCADE;
DROP TABLE IF EXISTS unifiles.extracted_assets CASCADE;
DROP TABLE IF EXISTS unifiles.extracted_documents CASCADE;
DROP TABLE IF EXISTS unifiles.processing_strategies CASCADE;

-- 文件管理层
DROP TABLE IF EXISTS unifiles.file_processing_logs CASCADE;
DROP TABLE IF EXISTS unifiles.files CASCADE;
DROP TABLE IF EXISTS unifiles.storage_configs CASCADE;

-- 用户层
DROP TABLE IF EXISTS unifiles.access_keys CASCADE;
DROP TABLE IF EXISTS unifiles.users CASCADE;

-- ================================
-- 删除物化视图
-- ================================

DROP MATERIALIZED VIEW IF EXISTS unifiles.mv_processing_chains CASCADE;

-- ================================
-- 删除视图
-- ================================

DROP VIEW IF EXISTS unifiles.active_tasks CASCADE;
DROP VIEW IF EXISTS unifiles.recent_failed_tasks CASCADE;

-- ================================
-- 删除函数
-- ================================

-- 触发器函数
DROP FUNCTION IF EXISTS unifiles.update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS unifiles.calculate_duration_ms() CASCADE;
DROP FUNCTION IF EXISTS unifiles.update_document_performance_metrics() CASCADE;
DROP FUNCTION IF EXISTS unifiles.set_task_queued_time() CASCADE;
DROP FUNCTION IF EXISTS unifiles.set_task_started_time() CASCADE;
DROP FUNCTION IF EXISTS unifiles.set_task_completed_time() CASCADE;
DROP FUNCTION IF EXISTS unifiles.update_kb_document_count() CASCADE;
DROP FUNCTION IF EXISTS unifiles.auto_update_kb_statistics() CASCADE;
DROP FUNCTION IF EXISTS unifiles.update_kb_total_chunks() CASCADE;

-- 辅助函数
DROP FUNCTION IF EXISTS unifiles.get_processing_chain(TEXT) CASCADE;
DROP FUNCTION IF EXISTS unifiles.get_processing_stats(TIMESTAMPTZ, TIMESTAMPTZ) CASCADE;
DROP FUNCTION IF EXISTS unifiles.get_user_pending_tasks_count(TEXT) CASCADE;
DROP FUNCTION IF EXISTS unifiles.get_task_duration_seconds(TEXT) CASCADE;
DROP FUNCTION IF EXISTS unifiles.cleanup_expired_tasks() CASCADE;
DROP FUNCTION IF EXISTS unifiles.get_task_statistics(TEXT, TIMESTAMPTZ, TIMESTAMPTZ) CASCADE;

-- ================================
-- 删除 Schema（可选，如果需要完全清理）
-- ================================

-- 注意：如果删除 schema，下次需要重新创建
-- DROP SCHEMA IF EXISTS unifiles CASCADE;

-- 如果不删除 schema，可以删除 pgvector 扩展
-- DROP EXTENSION IF EXISTS vector CASCADE;
-- DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;

-- ================================
-- 输出提示
-- ================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '数据库清理完成！';
    RAISE NOTICE '所有表、视图、函数已删除。';
    RAISE NOTICE '========================================';
END $$;
