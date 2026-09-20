# 数据库架构

本文档详细介绍 Unifiles 的数据库设计，包括表结构、索引策略和 pgvector 配置。

## 数据库技术栈

```
PostgreSQL 15+
├── pgvector 扩展 (向量存储)
├── pg_trgm 扩展 (模糊搜索)
└── uuid-ossp 扩展 (UUID 生成)
```

## 核心表结构

### 用户与认证

#### users 表

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    
    -- 配额设置
    storage_quota_bytes BIGINT DEFAULT 10737418240,  -- 10GB
    api_calls_quota INT DEFAULT 10000,
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;
```

#### api_keys 表

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 密钥信息 (存储哈希值，不存储明文)
    key_prefix VARCHAR(12) NOT NULL,  -- 如 "<api-key>"
    key_hash VARCHAR(255) NOT NULL,   -- bcrypt 哈希
    
    -- 元数据
    name VARCHAR(100),
    description TEXT,
    
    -- 权限与限制
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    rate_limit INT DEFAULT 1000,  -- 每分钟请求数
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;
```

### Layer 1: 文件存储

#### files 表

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 文件信息
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    
    -- 存储位置
    storage_bucket VARCHAR(100) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,
    
    -- 文件哈希 (用于去重)
    content_hash VARCHAR(64),  -- SHA-256
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- 状态
    status VARCHAR(20) DEFAULT 'uploaded',
    -- uploaded, processing, ready, error, deleted
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_files_user ON files(user_id);
CREATE INDEX idx_files_status ON files(status);
CREATE INDEX idx_files_hash ON files(content_hash);
CREATE INDEX idx_files_created ON files(created_at DESC);
CREATE INDEX idx_files_metadata ON files USING GIN(metadata);
CREATE INDEX idx_files_tags ON files USING GIN(tags);

-- 软删除过滤
CREATE INDEX idx_files_active ON files(user_id, status) 
    WHERE deleted_at IS NULL;
```

### Layer 2: 内容提取

#### extracted_contents 表

```sql
CREATE TABLE extracted_contents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    
    -- 提取内容 (Markdown 为单一事实来源)
    markdown_content TEXT NOT NULL,
    plain_text TEXT,  -- 用于全文搜索
    
    -- 提取元数据
    extraction_mode VARCHAR(20) NOT NULL,  -- simple, normal, advanced
    ocr_provider VARCHAR(50),
    ocr_config JSONB DEFAULT '{}',
    
    -- 文档结构
    page_count INT,
    word_count INT,
    char_count INT,
    language VARCHAR(10),
    
    -- 结构化数据
    headings JSONB DEFAULT '[]',
    tables JSONB DEFAULT '[]',
    images JSONB DEFAULT '[]',
    
    -- 处理信息
    processing_time_ms INT,
    extraction_version VARCHAR(20),
    
    -- 状态
    status VARCHAR(20) DEFAULT 'pending',
    -- pending, processing, completed, failed
    error_message TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_extractions_file ON extracted_contents(file_id);
CREATE INDEX idx_extractions_status ON extracted_contents(status);

-- 全文搜索索引
CREATE INDEX idx_extractions_fts ON extracted_contents 
    USING GIN(to_tsvector('english', plain_text));
```

#### file_processing_logs 表

```sql
CREATE TABLE file_processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    extraction_id UUID REFERENCES extracted_contents(id),
    
    -- 处理阶段
    stage VARCHAR(50) NOT NULL,
    -- validation, conversion, ocr, post_processing
    
    -- 状态
    status VARCHAR(20) NOT NULL,
    -- started, completed, failed, skipped
    
    -- 详情
    message TEXT,
    details JSONB DEFAULT '{}',
    duration_ms INT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_processing_logs_file ON file_processing_logs(file_id);
CREATE INDEX idx_processing_logs_extraction ON file_processing_logs(extraction_id);
CREATE INDEX idx_processing_logs_stage ON file_processing_logs(stage);
```

### Layer 3: 知识库

#### knowledge_bases 表

```sql
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 基本信息
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- 配置
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    embedding_dimensions INT DEFAULT 1536,
    
    -- 默认分块策略
    default_chunking_strategy VARCHAR(20) DEFAULT 'semantic',
    default_chunk_size INT DEFAULT 512,
    default_chunk_overlap INT DEFAULT 50,
    
    -- 统计
    document_count INT DEFAULT 0,
    chunk_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_kb_user ON knowledge_bases(user_id);
CREATE INDEX idx_kb_active ON knowledge_bases(is_active) WHERE is_active = true;
CREATE UNIQUE INDEX idx_kb_user_name ON knowledge_bases(user_id, name);
```

#### documents 表

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES files(id),
    extracted_content_id UUID NOT NULL REFERENCES extracted_contents(id),
    
    -- 分块配置 (可覆盖知识库默认值)
    chunking_strategy VARCHAR(20) NOT NULL,
    chunk_size INT NOT NULL,
    chunk_overlap INT NOT NULL,
    
    -- 文档元数据
    title VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- 统计
    chunk_count INT DEFAULT 0,
    token_count INT DEFAULT 0,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'pending',
    -- pending, processing, indexed, failed
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    indexed_at TIMESTAMP WITH TIME ZONE
);

-- 索引
CREATE INDEX idx_docs_kb ON documents(knowledge_base_id);
CREATE INDEX idx_docs_file ON documents(file_id);
CREATE INDEX idx_docs_status ON documents(status);
CREATE INDEX idx_docs_metadata ON documents USING GIN(metadata);
CREATE INDEX idx_docs_tags ON documents USING GIN(tags);

-- 防止同一文件重复添加到知识库
CREATE UNIQUE INDEX idx_docs_kb_file ON documents(knowledge_base_id, file_id);
```

#### chunks 表 (向量存储)

```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    
    -- 分块内容
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    
    -- 位置信息
    chunk_index INT NOT NULL,
    start_char INT,
    end_char INT,
    page_numbers INT[],
    
    -- 向量嵌入 (pgvector)
    embedding vector(1536),  -- 维度根据模型调整
    
    -- 元数据 (继承自文档)
    metadata JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 标准索引
CREATE INDEX idx_chunks_doc ON chunks(document_id);
CREATE INDEX idx_chunks_kb ON chunks(knowledge_base_id);
CREATE INDEX idx_chunks_index ON chunks(document_id, chunk_index);

-- 向量搜索索引 (HNSW - 推荐用于生产环境)
CREATE INDEX idx_chunks_embedding ON chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 备选: IVFFlat 索引 (适合大规模数据)
-- CREATE INDEX idx_chunks_embedding_ivf ON chunks 
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);
```

### Webhook 与事件

#### webhooks 表

```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 配置
    url VARCHAR(500) NOT NULL,
    events TEXT[] NOT NULL,
    secret VARCHAR(64) NOT NULL,
    
    -- 元数据
    description TEXT,
    metadata JSONB DEFAULT '{}',
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    
    -- 统计
    total_deliveries INT DEFAULT 0,
    successful_deliveries INT DEFAULT 0,
    failed_deliveries INT DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_webhooks_user ON webhooks(user_id);
CREATE INDEX idx_webhooks_active ON webhooks(is_active) WHERE is_active = true;
```

#### webhook_deliveries 表

```sql
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    
    -- 事件信息
    event_type VARCHAR(50) NOT NULL,
    event_id UUID NOT NULL,
    
    -- 请求
    request_body JSONB NOT NULL,
    request_headers JSONB,
    
    -- 响应
    response_status INT,
    response_body TEXT,
    response_time_ms INT,
    
    -- 重试信息
    attempt_number INT DEFAULT 1,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    
    -- 状态
    status VARCHAR(20) NOT NULL,
    -- pending, success, failed, exhausted
    error_message TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivered_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_deliveries_webhook ON webhook_deliveries(webhook_id);
CREATE INDEX idx_deliveries_status ON webhook_deliveries(status);
CREATE INDEX idx_deliveries_retry ON webhook_deliveries(next_retry_at) 
    WHERE status = 'failed';
```

## pgvector 配置

### 扩展安装

```sql
-- 安装 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证安装
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 向量维度

不同嵌入模型的维度配置：

| 模型 | 维度 | 说明 |
|------|------|------|
| text-embedding-3-small | 1536 | OpenAI 默认 |
| text-embedding-3-large | 3072 | OpenAI 高精度 |
| text-embedding-ada-002 | 1536 | OpenAI 旧版 |
| voyage-2 | 1024 | Voyage AI |
| bge-large-zh | 1024 | 中文优化 |

### 距离度量

```sql
-- 余弦相似度 (推荐)
SELECT * FROM chunks 
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- 欧氏距离
SELECT * FROM chunks 
ORDER BY embedding <-> query_embedding
LIMIT 10;

-- 内积
SELECT * FROM chunks 
ORDER BY embedding <#> query_embedding
LIMIT 10;
```

### 索引选择指南

#### HNSW 索引

适用场景：
- 数据量 < 1000 万条
- 需要高召回率
- 可接受较大内存占用

```sql
CREATE INDEX idx_hnsw ON chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (
        m = 16,              -- 每层连接数
        ef_construction = 64 -- 构建时搜索范围
    );

-- 查询时设置 ef_search
SET hnsw.ef_search = 100;
```

#### IVFFlat 索引

适用场景：
- 数据量 > 1000 万条
- 内存受限
- 可接受略低的召回率

```sql
-- 需要先有数据才能创建
CREATE INDEX idx_ivf ON chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- sqrt(n) 为经验值

-- 查询时设置 probes
SET ivfflat.probes = 10;
```

## 性能优化

### 分区策略

对于大规模部署，按知识库分区：

```sql
-- 创建分区表
CREATE TABLE chunks_partitioned (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    knowledge_base_id UUID NOT NULL,
    content TEXT NOT NULL,
    token_count INT NOT NULL,
    chunk_index INT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (id, knowledge_base_id)
) PARTITION BY HASH (knowledge_base_id);

-- 创建分区
CREATE TABLE chunks_p0 PARTITION OF chunks_partitioned
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE chunks_p1 PARTITION OF chunks_partitioned
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE chunks_p2 PARTITION OF chunks_partitioned
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE chunks_p3 PARTITION OF chunks_partitioned
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

### 连接池配置

```python
# PostgreSQL 连接池推荐配置
pool_config = {
    "min_size": 5,
    "max_size": 20,
    "max_queries": 50000,
    "max_inactive_connection_lifetime": 300,
    "command_timeout": 60
}
```

### 查询优化

```sql
-- 向量搜索 + 元数据过滤
SELECT c.id, c.content, 
       1 - (c.embedding <=> $1) as similarity
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE c.knowledge_base_id = $2
  AND d.metadata @> $3  -- JSONB 包含查询
ORDER BY c.embedding <=> $1
LIMIT $4;

-- 创建复合索引加速过滤
CREATE INDEX idx_chunks_kb_embedding ON chunks(knowledge_base_id) 
    INCLUDE (embedding);
```

## 数据迁移

### 添加新向量维度

```sql
-- 添加新的向量列
ALTER TABLE chunks ADD COLUMN embedding_3072 vector(3072);

-- 批量更新嵌入
UPDATE chunks SET embedding_3072 = compute_embedding(content)
WHERE embedding_3072 IS NULL;

-- 创建新索引
CREATE INDEX CONCURRENTLY idx_chunks_embedding_3072 ON chunks 
    USING hnsw (embedding_3072 vector_cosine_ops);

-- 切换后删除旧列
ALTER TABLE chunks DROP COLUMN embedding;
ALTER TABLE chunks RENAME COLUMN embedding_3072 TO embedding;
```

### 版本化迁移脚本

迁移脚本位于 `scripts/sql/` 目录：

```
scripts/sql/
├── 011-create-extensions.sql
├── 021-create-users.sql
├── 031-create-file-management.sql
├── 041-create-extractions.sql
├── 051-create-knowledge-bases.sql
├── 061-create-webhooks.sql
└── 071-create-indexes.sql
```

执行顺序：

```bash
# 按顺序执行所有迁移
for f in scripts/sql/*.sql; do
    psql -U postgres -d unifiles -f "$f"
done
```

## 备份策略

### 逻辑备份

```bash
# 完整备份
pg_dump -U postgres -d unifiles -F c -f backup.dump

# 仅备份 schema
pg_dump -U postgres -d unifiles -s -f schema.sql

# 备份特定表
pg_dump -U postgres -d unifiles -t chunks -F c -f chunks.dump
```

### 向量数据导出

```sql
-- 导出向量为 CSV
COPY (
    SELECT id, document_id, 
           embedding::text as embedding_text
    FROM chunks
) TO '/tmp/chunks_export.csv' WITH CSV HEADER;
```

## 监控查询

```sql
-- 表大小统计
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 索引使用情况
SELECT 
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 向量索引状态
SELECT * FROM pg_stat_user_indexes 
WHERE indexrelname LIKE '%embedding%';
```

## 下一步

- [存储架构](./storage-architecture.md) - MinIO 对象存储配置
- [安全模型](./security-model.md) - 认证与授权设计
