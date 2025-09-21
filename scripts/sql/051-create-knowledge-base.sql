/*
 * 文件名: 051-create-knowledge-base.sql
 * 作用: 创建知识库层表结构
 * 分类: 知识库层
 * 执行顺序: 第五步 - 在内容提取表创建后执行
 * 
 * 功能说明:
 * 1. knowledge_bases表: 存储知识库的基本信息和配置
 * 2. documents表: 存储知识库中的文档实例
 * 3. 支持知识库的层级管理和分组
 * 4. 灵活的分块策略配置
 * 
 * 设计原则:
 * - 知识库与提取文档解耦，支持同一文档加入多个知识库
 * - 支持文档级和知识库级的分块策略配置
 * - 完整的状态跟踪和统计信息
 * - 层级路径支持复杂的知识组织
 */

-- ================================
-- 知识库管理表 (Knowledge Bases)
-- ================================

-- 知识库表
CREATE TABLE IF NOT EXISTS unifiles.knowledge_bases (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 知识库唯一标识
    
    -- 用户关联
    user_id TEXT NOT NULL,                                 -- 知识库所有者
    
    -- 基本信息
    name TEXT NOT NULL,                                    -- 知识库名称
    display_name TEXT,                                     -- 显示名称
    description TEXT,                                      -- 知识库描述
    
    -- 知识库配置
    kb_type TEXT DEFAULT 'general',                       -- 知识库类型
    kb_category TEXT,                                      -- 知识库分类
    visibility TEXT DEFAULT 'private',                    -- 可见性
    access_level TEXT DEFAULT 'owner_only',               -- 访问级别
    
    -- 默认分块策略配置
    default_chunking_strategy JSONB DEFAULT '{
        "strategy_type": "markdown_hierarchical",
        "max_chunk_size": 1000,
        "overlap_size": 100,
        "preserve_structure": true,
        "split_on_headers": true,
        "min_chunk_size": 50,
        "chunk_overlap_strategy": "sentence_boundary"
    }',
    
    -- 向量配置
    vector_config JSONB DEFAULT '{
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
        "similarity_threshold": 0.7,
        "search_strategy": "hybrid"
    }',
    
    -- 搜索配置
    search_config JSONB DEFAULT '{
        "enable_semantic_search": true,
        "enable_keyword_search": true,
        "enable_hybrid_search": true,
        "rerank_enabled": false,
        "max_results": 20
    }',
    
    -- 知识库统计
    document_count INTEGER DEFAULT 0,                      -- 文档数量
    component_count INTEGER DEFAULT 0,                     -- 组件总数
    chunk_count INTEGER DEFAULT 0,                         -- 文本块数量
    photo_count INTEGER DEFAULT 0,                         -- 图片数量
    total_size_bytes BIGINT DEFAULT 0,                     -- 总大小（字节）
    
    -- 关联信息
    document_ids TEXT[] DEFAULT '{}',                       -- 关联的文档ID列表
    
    -- 层级信息
    parent_kb_id TEXT,                                     -- 父知识库ID（支持嵌套）
    hierarchy_path ltree DEFAULT 'root'::ltree,            -- 知识库层次路径
    hierarchy_level INTEGER DEFAULT 0,                     -- 层级深度
    
    -- 状态信息
    status TEXT DEFAULT 'active',                         -- 知识库状态
    processing_status TEXT DEFAULT 'ready',               -- 处理状态
    last_updated_by TEXT,                                 -- 最后更新者
    
    -- 元数据
    kb_metadata JSONB DEFAULT '{}',                       -- 知识库元数据
    tags TEXT[] DEFAULT '{}',                              -- 标签
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 更新时间
    last_document_added_at TIMESTAMPTZ,                   -- 最后添加文档时间
    last_processed_at TIMESTAMPTZ,                        -- 最后处理时间
    
    -- 外键约束
    CONSTRAINT fk_knowledge_bases_user_id 
        FOREIGN KEY (user_id) REFERENCES unifiles.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_bases_parent_kb_id 
        FOREIGN KEY (parent_kb_id) REFERENCES unifiles.knowledge_bases(id) ON DELETE SET NULL,
    CONSTRAINT fk_knowledge_bases_last_updated_by 
        FOREIGN KEY (last_updated_by) REFERENCES unifiles.users(id),
    
    -- 检查约束
    CONSTRAINT chk_knowledge_bases_kb_type 
        CHECK (kb_type IN ('general', 'specialized', 'personal', 'team', 'public', 'archive')),
    CONSTRAINT chk_knowledge_bases_visibility 
        CHECK (visibility IN ('private', 'shared', 'public', 'internal')),
    CONSTRAINT chk_knowledge_bases_access_level 
        CHECK (access_level IN ('owner_only', 'read_only', 'read_write', 'admin')),
    CONSTRAINT chk_knowledge_bases_status 
        CHECK (status IN ('active', 'inactive', 'archived', 'deleted')),
    CONSTRAINT chk_knowledge_bases_processing_status 
        CHECK (processing_status IN ('ready', 'processing', 'updating', 'indexing', 'error')),
    CONSTRAINT chk_knowledge_bases_hierarchy_level_positive 
        CHECK (hierarchy_level >= 0),
    -- 防止自引用
    CONSTRAINT chk_knowledge_bases_no_self_reference 
        CHECK (id != parent_kb_id)
);

-- ================================
-- 知识库文档表 (Knowledge Base Documents)
-- ================================

-- 知识库文档表（知识库中的文档实例）
CREATE TABLE IF NOT EXISTS unifiles.documents (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 文档实例唯一标识
    
    -- 关联信息
    knowledge_base_id TEXT NOT NULL,                       -- 知识库ID
    extracted_document_id TEXT NOT NULL,                   -- 提取文档ID（引用）
    
    -- 文档在知识库中的信息
    title TEXT,                                            -- 文档标题（可自定义）
    display_name TEXT,                                     -- 显示名称
    description TEXT,                                      -- 文档描述
    
    -- 分类和标签
    document_category TEXT,                                -- 文档分类
    tags TEXT[] DEFAULT '{}',                              -- 文档标签
    keywords TEXT[] DEFAULT '{}',                          -- 关键词
    
    -- 分块策略（可覆盖知识库默认策略）
    chunking_strategy JSONB,                               -- 文档级分块策略
    custom_config JSONB DEFAULT '{}',                      -- 自定义配置
    
    -- 处理状态
    processing_status TEXT DEFAULT 'pending',              -- 处理状态
    indexing_status TEXT DEFAULT 'pending',                -- 索引状态
    validation_status TEXT DEFAULT 'pending',              -- 验证状态
    
    -- 统计信息
    component_count INTEGER DEFAULT 0,                     -- 组件总数
    chunk_count INTEGER DEFAULT 0,                         -- 文本块数
    photo_count INTEGER DEFAULT 0,                         -- 图片数
    total_chars INTEGER DEFAULT 0,                         -- 总字符数
    total_tokens INTEGER DEFAULT 0,                        -- 总token数
    
    -- 内容统计（移除质量评估）
    
    -- 权限和访问
    document_permissions JSONB DEFAULT '{}',               -- 文档权限
    access_level TEXT DEFAULT 'inherited',                -- 访问级别
    
    -- 层次信息
    hierarchy_path ltree DEFAULT 'root'::ltree,            -- 文档层次路径
    parent_document_id TEXT,                               -- 父文档ID（支持文档层级）
    document_order INTEGER DEFAULT 0,                      -- 文档排序
    
    -- 版本信息
    version_number INTEGER DEFAULT 1,                      -- 版本号
    is_latest_version BOOLEAN DEFAULT TRUE,                -- 是否最新版本
    
    -- 使用统计
    view_count INTEGER DEFAULT 0,                         -- 查看次数
    search_count INTEGER DEFAULT 0,                       -- 搜索次数
    reference_count INTEGER DEFAULT 0,                    -- 引用次数
    
    -- 元数据
    document_metadata JSONB DEFAULT '{}',                 -- 文档元数据
    processing_metadata JSONB DEFAULT '{}',               -- 处理元数据
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    processed_at TIMESTAMPTZ,                              -- 处理完成时间
    indexed_at TIMESTAMPTZ,                                -- 索引完成时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 更新时间
    last_accessed_at TIMESTAMPTZ,                         -- 最后访问时间
    
    -- 外键约束
    CONSTRAINT fk_documents_knowledge_base_id 
        FOREIGN KEY (knowledge_base_id) REFERENCES unifiles.knowledge_bases(id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_extracted_document_id 
        FOREIGN KEY (extracted_document_id) REFERENCES unifiles.extracted_documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_parent_document_id 
        FOREIGN KEY (parent_document_id) REFERENCES unifiles.documents(id) ON DELETE SET NULL,
    
    -- 检查约束
    CONSTRAINT chk_documents_processing_status 
        CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    CONSTRAINT chk_documents_indexing_status 
        CHECK (indexing_status IN ('pending', 'indexing', 'completed', 'failed')),
    CONSTRAINT chk_documents_validation_status 
        CHECK (validation_status IN ('pending', 'validating', 'passed', 'failed', 'warning')),
    CONSTRAINT chk_documents_access_level 
        CHECK (access_level IN ('inherited', 'owner_only', 'read_only', 'read_write', 'admin')),
    CONSTRAINT chk_documents_version_number_positive 
        CHECK (version_number > 0),
    -- 防止自引用
    CONSTRAINT chk_documents_no_self_reference 
        CHECK (id != parent_document_id),
    
    -- 确保同一个提取文档在同一个知识库中只能有一个实例
    UNIQUE (knowledge_base_id, extracted_document_id)
);


-- ================================
-- 知识库统计表 (Knowledge Base Statistics)
-- ================================

-- 知识库统计表
CREATE TABLE IF NOT EXISTS unifiles.kb_statistics (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 统计记录ID
    
    -- 知识库关联
    knowledge_base_id TEXT NOT NULL,                       -- 知识库ID
    
    -- 基础统计
    total_documents INTEGER DEFAULT 0,                     -- 文档总数
    total_components INTEGER DEFAULT 0,                    -- 组件总数
    total_chunks INTEGER DEFAULT 0,                        -- 文本块总数
    total_photos INTEGER DEFAULT 0,                        -- 图片总数
    
    -- 内容统计
    total_characters BIGINT DEFAULT 0,                     -- 总字符数
    total_words BIGINT DEFAULT 0,                          -- 总词数
    total_tokens BIGINT DEFAULT 0,                         -- 总token数
    total_size_bytes BIGINT DEFAULT 0,                     -- 总大小（字节）
    
    -- 内容统计（移除质量评估）
    
    -- 使用统计
    total_searches BIGINT DEFAULT 0,                       -- 总搜索次数
    total_views BIGINT DEFAULT 0,                          -- 总查看次数
    unique_users_count INTEGER DEFAULT 0,                  -- 独立用户数
    
    -- 性能统计
    avg_search_time_ms INTEGER,                           -- 平均搜索时间
    avg_indexing_time_ms INTEGER,                         -- 平均索引时间
    
    -- 时间统计
    last_document_added_at TIMESTAMPTZ,                   -- 最后添加文档时间
    last_search_at TIMESTAMPTZ,                           -- 最后搜索时间
    last_updated_at TIMESTAMPTZ,                          -- 最后更新时间
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_kb_statistics_knowledge_base_id 
        FOREIGN KEY (knowledge_base_id) REFERENCES unifiles.knowledge_bases(id) ON DELETE CASCADE,
    
    -- 唯一约束
    UNIQUE (knowledge_base_id)
);

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为knowledge_bases表添加更新时间戳触发器
DROP TRIGGER IF EXISTS trigger_knowledge_bases_updated_at ON unifiles.knowledge_bases;
CREATE TRIGGER trigger_knowledge_bases_updated_at
    BEFORE UPDATE ON unifiles.knowledge_bases
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为documents表添加更新时间戳触发器
DROP TRIGGER IF EXISTS trigger_documents_updated_at ON unifiles.documents;
CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON unifiles.documents
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();


-- 为kb_statistics表添加更新时间戳触发器
DROP TRIGGER IF EXISTS trigger_kb_statistics_updated_at ON unifiles.kb_statistics;
CREATE TRIGGER trigger_kb_statistics_updated_at
    BEFORE UPDATE ON unifiles.kb_statistics
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();