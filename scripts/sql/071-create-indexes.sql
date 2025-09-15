/*
 * 文件名: 071-create-indexes.sql
 * 作用: 创建数据库索引和性能优化
 * 分类: 索引和性能优化
 * 执行顺序: 第七步 - 在所有表创建后执行
 * 
 * 功能说明:
 * 1. 为所有表创建必要的索引以提升查询性能
 * 2. 创建复合索引支持复杂查询
 * 3. 创建向量搜索索引支持语义搜索
 * 4. 创建全文搜索索引支持关键词搜索（中英文）
 * 5. 创建唯一索引保证数据完整性
 * 
 * 设计原则:
 * - 根据查询模式优化索引策略
 * - 平衡查询性能和写入性能
 * - 支持多种搜索方式（向量、全文、精确匹配）
 * - 考虑索引维护成本
 * 
 * 依赖要求:
 * - PGroonga扩展：用于中英文全文搜索支持
 * - pgvector扩展：用于向量搜索支持
 * 
 * 注意事项:
 * - 如果PGroonga扩展未安装，可以跳过pgroonga索引，使用备用的gin索引
 * - 向量索引需要pgvector扩展支持
 */

-- ================================
-- 用户和权限相关索引 (User & Permission Indexes)
-- ================================

-- 用户表索引（简化后的用户表只保留基本字段）
CREATE INDEX IF NOT EXISTS idx_users_created_at ON chunk_schema.users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_knowledge_ids ON chunk_schema.users USING gin(knowledge_ids);

-- 用户会话表和用户活动日志表已被移除，无需索引

-- ================================
-- 存储配置相关索引 (Storage Configuration Indexes)
-- ================================

-- 存储配置表索引
CREATE INDEX IF NOT EXISTS idx_storage_configs_storage_name ON chunk_schema.storage_configs(storage_name);
CREATE INDEX IF NOT EXISTS idx_storage_configs_storage_type ON chunk_schema.storage_configs(storage_type);
CREATE INDEX IF NOT EXISTS idx_storage_configs_is_active ON chunk_schema.storage_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_storage_configs_is_default ON chunk_schema.storage_configs(is_default);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_storage_configs_active_default ON chunk_schema.storage_configs(is_active, is_default);
CREATE INDEX IF NOT EXISTS idx_storage_configs_type_active ON chunk_schema.storage_configs(storage_type, is_active);

-- ================================
-- 文件管理相关索引 (File Management Indexes)
-- ================================

-- 文件表索引（基于简化后的文件表结构）
CREATE INDEX IF NOT EXISTS idx_files_user_id ON chunk_schema.files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_status ON chunk_schema.files(status);
CREATE INDEX IF NOT EXISTS idx_files_mime_type ON chunk_schema.files(mime_type) WHERE mime_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_files_hash ON chunk_schema.files(file_hash) WHERE file_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_files_created_at ON chunk_schema.files(created_at);
CREATE INDEX IF NOT EXISTS idx_files_filename ON chunk_schema.files(filename);

-- 存储配置支持索引
CREATE INDEX IF NOT EXISTS idx_files_storage_config_id ON chunk_schema.files(storage_config_id) WHERE storage_config_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_files_storage_path ON chunk_schema.files(storage_path);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_files_user_status ON chunk_schema.files(user_id, status);
CREATE INDEX IF NOT EXISTS idx_files_status_created ON chunk_schema.files(status, created_at);
CREATE INDEX IF NOT EXISTS idx_files_storage_config_user ON chunk_schema.files(storage_config_id, user_id) WHERE storage_config_id IS NOT NULL;

-- 文件处理日志表索引
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_file_id ON chunk_schema.file_processing_logs(file_id);
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_stage ON chunk_schema.file_processing_logs(stage);
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_status ON chunk_schema.file_processing_logs(status);
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_created_at ON chunk_schema.file_processing_logs(created_at);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_file_stage ON chunk_schema.file_processing_logs(file_id, stage);
CREATE INDEX IF NOT EXISTS idx_file_processing_logs_stage_status ON chunk_schema.file_processing_logs(stage, status);

-- 文件版本表已被移除
-- 文件统计表已被移除

-- ================================
-- 内容提取相关索引 (Content Extraction Indexes)
-- ================================

-- 提取文档表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_extracted_documents_file_id ON chunk_schema.extracted_documents(file_id);
CREATE INDEX IF NOT EXISTS idx_extracted_documents_user_id ON chunk_schema.extracted_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_extracted_documents_method ON chunk_schema.extracted_documents(extraction_method);
CREATE INDEX IF NOT EXISTS idx_extracted_documents_created_at ON chunk_schema.extracted_documents(created_at);

-- 全文搜索索引 (使用PGroonga支持中英文搜索)
CREATE INDEX IF NOT EXISTS idx_extracted_documents_fts_pgroonga ON chunk_schema.extracted_documents USING pgroonga (full_markdown) WHERE full_markdown IS NOT NULL;
-- 备用英文搜索索引
CREATE INDEX IF NOT EXISTS idx_extracted_documents_fts ON chunk_schema.extracted_documents USING gin(to_tsvector('english', full_markdown)) WHERE full_markdown IS NOT NULL;

-- 提取资源表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_extracted_assets_document_id ON chunk_schema.extracted_assets(extracted_document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_assets_type ON chunk_schema.extracted_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_extracted_assets_position ON chunk_schema.extracted_assets(position_in_document) WHERE position_in_document IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_extracted_assets_format ON chunk_schema.extracted_assets(format) WHERE format IS NOT NULL;

-- 存储配置支持索引
CREATE INDEX IF NOT EXISTS idx_extracted_assets_storage_config_id ON chunk_schema.extracted_assets(storage_config_id) WHERE storage_config_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_extracted_assets_storage_path ON chunk_schema.extracted_assets(storage_path);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_extracted_assets_document_type ON chunk_schema.extracted_assets(extracted_document_id, asset_type);
CREATE INDEX IF NOT EXISTS idx_extracted_assets_storage_config_type ON chunk_schema.extracted_assets(storage_config_id, asset_type) WHERE storage_config_id IS NOT NULL;

-- 文档页面信息表和提取日志表已被移除

-- ================================
-- 知识库相关索引 (Knowledge Base Indexes)
-- ================================

-- 知识库表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_user_id ON chunk_schema.knowledge_bases(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_name ON chunk_schema.knowledge_bases(name) WHERE name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_status ON chunk_schema.knowledge_bases(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_created_at ON chunk_schema.knowledge_bases(created_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_document_ids ON chunk_schema.knowledge_bases USING gin(document_ids) WHERE document_ids IS NOT NULL;

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_user_status ON chunk_schema.knowledge_bases(user_id, status) WHERE status IS NOT NULL;

-- 文档表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_documents_knowledge_base_id ON chunk_schema.documents(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_extracted_document_id ON chunk_schema.documents(extracted_document_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON chunk_schema.documents(status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_title ON chunk_schema.documents(title) WHERE title IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON chunk_schema.documents(created_at);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_documents_kb_status ON chunk_schema.documents(knowledge_base_id, status) WHERE status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_status_created ON chunk_schema.documents(status, created_at) WHERE status IS NOT NULL;

-- 知识库权限表和统计表已被移除

-- ================================
-- 组件抽象相关索引 (Component Abstraction Indexes)
-- ================================

-- 组件表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_components_document_id ON chunk_schema.components(document_id);
CREATE INDEX IF NOT EXISTS idx_components_type ON chunk_schema.components(component_type);
CREATE INDEX IF NOT EXISTS idx_components_index ON chunk_schema.components(component_index);
CREATE INDEX IF NOT EXISTS idx_components_created_at ON chunk_schema.components(created_at);

-- 向量搜索索引 - 使用IVFFlat算法进行高效向量搜索
CREATE INDEX IF NOT EXISTS idx_components_embedding ON chunk_schema.components USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 全文搜索索引（基于优化后的搜索字段，使用PGroonga支持中英文搜索）
CREATE INDEX IF NOT EXISTS idx_components_searchable_text_pgroonga ON chunk_schema.components USING pgroonga (searchable_text) WHERE searchable_text IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_components_content_pgroonga ON chunk_schema.components USING pgroonga (content) WHERE content IS NOT NULL;

-- 关键词搜索索引 (PGroonga支持TEXT[]类型的倒排检索)
CREATE INDEX IF NOT EXISTS idx_components_search_keywords_pgroonga ON chunk_schema.components USING pgroonga (search_keywords) WHERE search_keywords IS NOT NULL;
-- 备用GIN索引
CREATE INDEX IF NOT EXISTS idx_components_search_keywords ON chunk_schema.components USING gin(search_keywords) WHERE search_keywords IS NOT NULL;

-- 备用英文搜索索引
CREATE INDEX IF NOT EXISTS idx_components_content_fts ON chunk_schema.components USING gin(to_tsvector('english', COALESCE(searchable_text, content))) WHERE COALESCE(searchable_text, content) IS NOT NULL;

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_components_document_type ON chunk_schema.components(document_id, component_type);
CREATE INDEX IF NOT EXISTS idx_components_document_index ON chunk_schema.components(document_id, component_index);

-- 文本块表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_chunks_component_id ON chunk_schema.chunks(component_id);
CREATE INDEX IF NOT EXISTS idx_chunks_char_count ON chunk_schema.chunks(char_count) WHERE char_count IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chunks_word_count ON chunk_schema.chunks(word_count) WHERE word_count IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chunks_token_count ON chunk_schema.chunks(token_count) WHERE token_count IS NOT NULL;

-- 全文搜索索引 (使用PGroonga支持中英文搜索)
CREATE INDEX IF NOT EXISTS idx_chunks_text_fts_pgroonga ON chunk_schema.chunks USING pgroonga (text_content) WHERE text_content IS NOT NULL;
-- 备用英文搜索索引
CREATE INDEX IF NOT EXISTS idx_chunks_text_fts ON chunk_schema.chunks USING gin(to_tsvector('english', text_content)) WHERE text_content IS NOT NULL;

-- 图片表索引（基于简化后的结构）
CREATE INDEX IF NOT EXISTS idx_photos_component_id ON chunk_schema.photos(component_id);
CREATE INDEX IF NOT EXISTS idx_photos_extracted_asset_id ON chunk_schema.photos(extracted_asset_id);
CREATE INDEX IF NOT EXISTS idx_photos_subtype ON chunk_schema.photos(photo_subtype);
CREATE INDEX IF NOT EXISTS idx_photos_width_height ON chunk_schema.photos(width, height) WHERE width IS NOT NULL AND height IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_photos_format ON chunk_schema.photos(format) WHERE format IS NOT NULL;

-- 组件关系表已被移除

-- ================================
-- 性能优化专用索引 (Performance Optimization Indexes)
-- ================================

-- 基于时间范围的查询优化
CREATE INDEX IF NOT EXISTS idx_files_created_at_desc ON chunk_schema.files(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_extracted_documents_completed_at_desc ON chunk_schema.extracted_documents(completed_at DESC) WHERE completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_components_created_at_desc ON chunk_schema.components(created_at DESC);

-- 统计查询优化索引
CREATE INDEX IF NOT EXISTS idx_files_user_status_created ON chunk_schema.files(user_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_components_document_type_created ON chunk_schema.components(document_id, component_type, created_at);

-- 搜索性能优化索引
CREATE INDEX IF NOT EXISTS idx_components_embedding_quality ON chunk_schema.components(embedding) WHERE embedding IS NOT NULL;

-- ================================
-- 分析和报表专用索引 (Analytics Indexes)
-- ================================

-- 文件上传分析
CREATE INDEX IF NOT EXISTS idx_files_upload_monthly ON chunk_schema.files(user_id, date_trunc('month', created_at));

-- 内容提取方法分析
CREATE INDEX IF NOT EXISTS idx_extracted_documents_method_created ON chunk_schema.extracted_documents(extraction_method, created_at);

-- ================================
-- 索引维护和监控 (Index Maintenance)
-- ================================

-- 为向量索引创建监控视图
CREATE OR REPLACE VIEW chunk_schema.vector_index_stats AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes 
WHERE indexname LIKE '%embedding%';

-- 创建索引使用统计视图
CREATE OR REPLACE VIEW chunk_schema.index_usage_stats AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    CASE 
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'LOW_USAGE'
        WHEN idx_scan < 1000 THEN 'MEDIUM_USAGE'
        ELSE 'HIGH_USAGE'
    END as usage_level
FROM pg_stat_user_indexes 
WHERE schemaname = 'chunk_schema'
ORDER BY idx_scan DESC;