/*
 * 文件名: 021-create-document-table.sql
 * 作用: 创建知识库主要数据表结构
 * 组成:
 * 1. chunk_schema - 总管理命名空间
 * 2. users - 用户表，存储用户信息和关联的知识库ID
 * 3. knowledge_bases - 知识库表，存储知识库基本信息和关联的文档ID
 * 4. documents - 文档表，存储文档信息和关联的组件(分块和图片)ID
 * 5. chunks - 文本分块表，存储文档的文本内容块
 * 6. photos - 图片表，存储文档中的图片和表格信息
 * 7. logical_hierarchy - 逻辑层级表，用于管理知识库内的标签层次
 * 8. components - 文档的成份表(分块和图片)
 */

-- 创建总管理schema
CREATE SCHEMA IF NOT EXISTS chunk_schema;

-- 创建用户-知识库管理
CREATE TABLE IF NOT EXISTS chunk_schema.users(
    id TEXT PRIMARY KEY,
    knowledge_ids TEXT[] DEFAULT '{}'
);

-- 创建知识库-文档管理
CREATE TABLE IF NOT EXISTS chunk_schema.knowledge_bases (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    document_ids TEXT[] DEFAULT '{}'::TEXT[]
);

-- 创建文档-分块管理
CREATE TABLE IF NOT EXISTS chunk_schema.documents (
    id TEXT PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES chunk_schema.knowledge_bases(id) ON DELETE CASCADE,
    name TEXT,
    text TEXT,                   -- 文档的完整文本内容，由components表自动生成
    component_ids TEXT[] DEFAULT '{}',
    hierarchy_path ltree DEFAULT 'root'::ltree,    -- 文档在知识库层级中的具体路径
    raw_file_public_url TEXT,
    markdown_public_url TEXT,
    upload_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    tags TEXT[] DEFAULT '{}'
);

-- 创建文档的成份表(分块和图片),由document_id和doc_position联合唯一
CREATE TABLE IF NOT EXISTS chunk_schema.components (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    doc_position INTEGER NOT NULL,
    type TEXT CHECK ( type IN ('chunk','photo','table')),
    text TEXT,
    embedding vector,           -- 文本的向量嵌入
    tsv tsvector,              -- 文本的倒排索引
    UNIQUE (document_id, doc_position)
);

-- 创建分块管理表
CREATE TABLE IF NOT EXISTS chunk_schema.chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    text TEXT,
    embedding vector,           -- 文本的向量嵌入
    doc_position INTEGER
);

-- 创建图片管理表
CREATE TABLE IF NOT EXISTS chunk_schema.photos (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    type TEXT CHECK ( type IN ('photo','table')),
    text TEXT,                  -- 对图片的详尽描述
    base64_image TEXT,          -- 图片的base64编码
    embedding vector,           -- 文本的向量嵌入
    doc_position INTEGER
);

-- 创建逻辑层级表
CREATE TABLE IF NOT EXISTS chunk_schema.logical_hierarchy (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    knowledge_base_id TEXT NOT NULL REFERENCES chunk_schema.knowledge_bases(id) ON DELETE CASCADE,
    labels JSONB NOT NULL DEFAULT '[]'
);