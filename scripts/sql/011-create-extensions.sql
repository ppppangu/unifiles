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
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 rum 插件 - 高级全文搜索索引
-- CREATE EXTENSION IF NOT EXISTS rum;
-- 启用 ltree 扩展 - 用于层级结构管理
CREATE EXTENSION IF NOT EXISTS ltree;

-- 倒排检索
CREATE EXTENSION IF NOT EXISTS pgroonga;

-- 创建主要的数据库模式
CREATE SCHEMA IF NOT EXISTS chunk_schema;

-- 注意: 生产环境中应该根据实际需要设置更严格的权限
GRANT USAGE ON SCHEMA chunk_schema TO PUBLIC;