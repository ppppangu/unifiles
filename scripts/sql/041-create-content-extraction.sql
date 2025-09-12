/*
 * 文件名: 041-create-content-extraction.sql
 * 作用: 创建内容提取层表结构
 * 分类: 内容提取层
 * 执行顺序: 第四步 - 在文件管理表创建后执行
 * 
 * 功能说明:
 * 1. extracted_documents表: 存储OCR后的完整文档内容
 * 2. extracted_assets表: 存储文档中提取的图片、表格等资源
 * 3. 提供无信息丢失的文档提取结果
 * 4. 为知识库层提供高质量的输入数据
 * 
 * 设计原则:
 * - 完整保存提取结果，不做任何裁剪
 * - 详细记录提取质量和置信度
 * - 支持多种提取方法和版本
 * - 资源与文档的关联关系清晰
 */

-- ================================
-- 提取文档表 (Extracted Documents)
-- ================================

-- 提取文档表（OCR后的完整文档）
CREATE TABLE IF NOT EXISTS chunk_schema.extracted_documents (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 提取文档唯一标识
    
    -- 源文件关联
    file_id TEXT NOT NULL,                                 -- 源文件ID
    user_id TEXT NOT NULL,                                 -- 用户ID（冗余，便于查询）
    
    -- 提取器信息
    extraction_method TEXT NOT NULL,                       -- 提取方法（如：mineru, tesseract, paddle）
    extraction_version TEXT,                               -- 提取器版本
    extraction_engine TEXT,                                -- 提取引擎（如：OCR引擎版本）
    
    -- 核心内容
    full_markdown TEXT NOT NULL,                           -- 完整markdown文档
    structured_content JSONB,                              -- 结构化内容（JSON格式）
    
    -- 文档结构信息
    document_structure JSONB DEFAULT '{}',                 -- 文档结构元数据
    page_structure JSONB DEFAULT '{}',                     -- 页面结构信息
    
    -- 文档统计
    total_pages INTEGER DEFAULT 0,                         -- 总页数
    total_chars INTEGER DEFAULT 0,                         -- 总字符数
    total_words INTEGER DEFAULT 0,                         -- 总词数
    total_paragraphs INTEGER DEFAULT 0,                    -- 总段落数
    total_assets INTEGER DEFAULT 0,                        -- 总资源数（图片、表格等）
    
    -- 内容分类统计
    text_blocks_count INTEGER DEFAULT 0,                   -- 文本块数量
    image_blocks_count INTEGER DEFAULT 0,                  -- 图片块数量
    
    -- 提取统计（移除质量评估）
    
    -- 处理状态
    extraction_status TEXT DEFAULT 'completed',            -- 提取状态
    
    -- 提取元数据
    extraction_metadata JSONB DEFAULT '{}',                -- 提取过程的详细元数据
    processing_config JSONB DEFAULT '{}',                  -- 处理配置信息
    performance_metrics JSONB DEFAULT '{}',                -- 性能指标
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    extraction_started_at TIMESTAMPTZ,                     -- 提取开始时间
    completed_at TIMESTAMPTZ,                              -- 提取完成时间
    validated_at TIMESTAMPTZ,                              -- 验证完成时间
    
    -- 外键约束
    CONSTRAINT fk_extracted_documents_file_id 
        FOREIGN KEY (file_id) REFERENCES chunk_schema.files(id) ON DELETE CASCADE,
    CONSTRAINT fk_extracted_documents_user_id 
        FOREIGN KEY (user_id) REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
        
    -- 检查约束
    CONSTRAINT chk_extracted_documents_extraction_status 
        CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed', 'partial')),

        
    -- 确保一个文件只有一个提取文档
    UNIQUE (file_id)
);

-- ================================
-- 提取资源表 (Extracted Assets)
-- ================================

-- 提取资源表（文档中的图片、表格等）
CREATE TABLE IF NOT EXISTS chunk_schema.extracted_assets (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 资源唯一标识
    
    -- 文档关联
    extracted_document_id TEXT NOT NULL,                   -- 提取文档ID
    
    -- 资源基本信息
    asset_type TEXT NOT NULL,                              -- 资源类型
    asset_subtype TEXT,                                    -- 资源子类型
    asset_name TEXT,                                       -- 资源名称
    original_filename TEXT,                                -- 原始文件名
    
    -- 存储信息（简化存储配置）
    storage_config_id TEXT,                                -- 存储配置ID（关联storage_configs表）
    storage_path TEXT NOT NULL,                           -- 存储路径（相对于配置的base_path）
    
    -- 文件属性
    file_size INTEGER,                                     -- 文件大小（字节）
    file_hash TEXT,                                        -- 文件哈希
    format TEXT,                                           -- 文件格式（jpg, png, svg等）
    mime_type TEXT,                                        -- MIME类型
    
    -- 位置信息
    position_in_document INTEGER,                          -- 在文档中的位置序号
    
    -- 内容信息
    asset_description TEXT,                                -- 资源描述
    extracted_text TEXT,                                  -- 从资源中提取的文本（如表格文本）
    alt_text TEXT,                                         -- 替代文本
    caption TEXT,                                          -- 标题/说明
    
    -- 基础属性（移除质量评估）
    extraction_confidence FLOAT,                          -- 提取置信度
    
    -- 处理状态
    processing_status TEXT DEFAULT 'extracted',           -- 处理状态
    validation_status TEXT DEFAULT 'pending',             -- 验证状态
    
    -- 资源元数据
    asset_metadata JSONB DEFAULT '{}',                    -- 资源详细元数据
    extraction_metadata JSONB DEFAULT '{}',               -- 提取过程元数据
    
    -- 使用统计
    access_count INTEGER DEFAULT 0,                       -- 访问次数
    reference_count INTEGER DEFAULT 0,                    -- 引用次数
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    extracted_at TIMESTAMPTZ,                             -- 提取时间
    last_accessed_at TIMESTAMPTZ,                         -- 最后访问时间
    
    -- 外键约束
    CONSTRAINT fk_extracted_assets_document_id 
        FOREIGN KEY (extracted_document_id) REFERENCES chunk_schema.extracted_documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_extracted_assets_storage_config_id 
        FOREIGN KEY (storage_config_id) REFERENCES chunk_schema.storage_configs(id) ON DELETE SET NULL,
    
    -- 检查约束
    CONSTRAINT chk_extracted_assets_type 
        CHECK (asset_type IN ('image', 'table', 'chart', 'diagram', 'formula', 'photo', 'drawing', 'signature')),

    CONSTRAINT chk_extracted_assets_processing_status 
        CHECK (processing_status IN ('extracted', 'processing', 'enhanced', 'failed')),
    CONSTRAINT chk_extracted_assets_validation_status 
        CHECK (validation_status IN ('pending', 'validating', 'passed', 'failed', 'warning')),
    CONSTRAINT chk_extracted_assets_confidence 
        CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)),
    CONSTRAINT chk_extracted_assets_file_size_positive 
        CHECK (file_size IS NULL OR file_size > 0)
);


-- ================================
-- 提取错误日志表 (Extraction Errors)
-- ================================

-- 提取错误和警告日志表
CREATE TABLE IF NOT EXISTS chunk_schema.extraction_logs (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 日志唯一标识
    
    -- 关联对象
    extracted_document_id TEXT,                            -- 提取文档ID（可选）
    extracted_asset_id TEXT,                               -- 提取资源ID（可选）
    file_id TEXT,                                          -- 源文件ID（可选）
    
    -- 日志信息
    log_level TEXT NOT NULL,                               -- 日志级别
    log_category TEXT NOT NULL,                            -- 日志分类
    log_message TEXT NOT NULL,                             -- 日志消息
    
    -- 错误详情
    error_code TEXT,                                       -- 错误代码
    error_details JSONB,                                   -- 错误详情
    stack_trace TEXT,                                      -- 堆栈跟踪
    
    -- 上下文信息
    context_info JSONB DEFAULT '{}',                       -- 上下文信息
    processing_stage TEXT,                                 -- 处理阶段
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    
    -- 外键约束（可选）
    CONSTRAINT fk_extraction_logs_document_id 
        FOREIGN KEY (extracted_document_id) REFERENCES chunk_schema.extracted_documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_extraction_logs_asset_id 
        FOREIGN KEY (extracted_asset_id) REFERENCES chunk_schema.extracted_assets(id) ON DELETE CASCADE,
    CONSTRAINT fk_extraction_logs_file_id 
        FOREIGN KEY (file_id) REFERENCES chunk_schema.files(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_extraction_logs_level 
        CHECK (log_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_extraction_logs_category 
        CHECK (log_category IN ('ocr', 'parsing', 'validation', 'enhancement', 'storage', 'system'))
);