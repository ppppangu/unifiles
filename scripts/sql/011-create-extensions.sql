/*
 * 文件名: 011-create-extensions.sql
 * 作用: 创建PostgreSQL必要的扩展插件和基础设置
 * 分类: 扩展和基础设置
 * 执行顺序: 第一步 - 必须在所有其他SQL文件之前执行
 * 
 * 功能说明:
 * 1. 向量化支持: pgvector - 用于向量嵌入存储和检索
 * 2. 全文检索: rum - 高级全文搜索索引
 * 3. 层级结构: ltree - 用于知识库和文档的层级管理
 */
-- ================================
-- 向量化扩展 (Vector Extensions)
-- ================================
-- 启用 pgvector 扩展 - 向量存储和相似性搜索
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
        RAISE NOTICE 'pgvector extension created successfully';
    ELSE
        RAISE EXCEPTION 'pgvector extension is not available. Please install pgvector first.';
    END IF;
END $$;

-- 启用 ltree 扩展 - 用于层级结构管理
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'ltree') THEN
        CREATE EXTENSION IF NOT EXISTS ltree;
        RAISE NOTICE 'ltree extension created successfully';
    ELSE
        RAISE EXCEPTION 'ltree extension is not available. Please install ltree first.';
    END IF;
END $$;

-- 启用 pgroonga 扩展 - 倒排检索（可选）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pgroonga') THEN
        CREATE EXTENSION IF NOT EXISTS pgroonga;
        RAISE NOTICE 'pgroonga extension created successfully';
    ELSE
        RAISE NOTICE 'pgroonga extension is not available, skipping. Full-text search will use standard GIN indexes.';
    END IF;
END $$;

-- 启用 rum 插件 - 高级全文搜索索引
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'rum') THEN
        CREATE EXTENSION IF NOT EXISTS rum;
        RAISE NOTICE 'rum extension created successfully';
    ELSE
        RAISE NOTICE 'rum extension is not available, skipping.';
    END IF;
END $$;

-- 创建主要的数据库模式
CREATE SCHEMA IF NOT EXISTS unifiles;

-- 注意: 生产环境中应该根据实际需要设置更严格的权限
GRANT USAGE ON SCHEMA unifiles TO PUBLIC;