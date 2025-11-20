/*
 * 文件名: 061-create-component-abstraction.sql
 * 作用: 创建组件抽象层表结构（简化版）
 * 分类: 组件抽象层
 * 执行顺序: 第六步 - 在知识库表创建后执行
 * 
 * 功能说明:
 * 1. components表: 统一的组件抽象，支持chunk和photo两种子类型
 * 2. chunks表: 文本块子类，存储核心文本属性
 * 3. photos表: 图片块子类，存储基本图片信息
 * 4. 实现组件的统一向量化和搜索能力
 * 
 * 设计原则:
 * - 保留核心功能，大幅简化字段
 * - 组件作为统一抽象，chunks和photos作为其子类实现
 * - 支持基本的向量搜索和内容检索
 * - 清晰的1:1关系保证数据一致性
 */

-- ================================
-- 向量维度配置说明 (Vector Dimension Configuration)
-- ================================

-- 常用嵌入模型维度参考：
-- text-embedding-3-small: 1536
-- text-embedding-3-large: 3072  
-- text-embedding-ada-002: 1536
-- 维度信息存储在 embedding_dimensions 列中

-- ================================
-- 组件抽象表 (Component Abstraction)
-- ================================

-- 组件表（文档分块后的统一组件抽象）
CREATE TABLE IF NOT EXISTS unifiles.components (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 组件唯一标识
    
    -- 文档关联
    document_id TEXT NOT NULL,                             -- 知识库文档ID
    
    -- 组件基本信息
    component_type TEXT NOT NULL,                          -- 组件类型（chunk/photo/audio/video）
    component_index INTEGER NOT NULL,                      -- 组件在文档中的序号
    
    -- 组件内容（统一字段）
    content TEXT,                                          -- 组件内容（文本或图片描述或视频描述）
    
    -- 搜索优化字段
    searchable_text TEXT,                                  -- 经过清洗和优化的搜索文本（去除markdown标记等）
    search_keywords TEXT[],                                -- 提取的关键词数组
    content_language TEXT DEFAULT 'mixed',                 -- 内容语言（zh/en/mixed）
    
    -- 向量索引（统一）
    embedding vector,                                     -- 向量嵌入（动态维度）
    embedding_dimensions INTEGER,                         -- 向量维度数（存储实际维度）
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_components_document_id 
        FOREIGN KEY (document_id) REFERENCES unifiles.documents(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_components_type 
        CHECK (component_type IN ('chunk', 'photo')),
    CONSTRAINT chk_components_component_index_positive 
        CHECK (component_index >= 0),
    CONSTRAINT chk_components_content_language 
        CHECK (content_language IN ('zh', 'en', 'mixed', 'unknown')),
    CONSTRAINT chk_components_embedding_dimensions_positive 
        CHECK (embedding_dimensions IS NULL OR embedding_dimensions > 0),
    CONSTRAINT chk_components_embedding_consistency
        CHECK ((embedding IS NULL AND embedding_dimensions IS NULL) OR 
               (embedding IS NOT NULL AND embedding_dimensions IS NOT NULL)),
    
    -- 确保组件在文档中的序号唯一
    UNIQUE (document_id, component_index)
);

-- ================================
-- 文本块子类表 (Text Chunks)
-- ================================

-- 文本块表（组件的文本子类）
CREATE TABLE IF NOT EXISTS unifiles.chunks (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 文本块唯一标识
    
    -- 组件关联
    component_id TEXT NOT NULL,                            -- 组件ID（1:1关系）
    
    -- 文本块核心属性
    text_content TEXT NOT NULL,                            -- 文本内容
    
    -- 文本统计
    char_count INTEGER,                                    -- 字符数
    token_count INTEGER,                                   -- token数
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,    -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,    -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_chunks_component_id 
        FOREIGN KEY (component_id) REFERENCES unifiles.components(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_chunks_char_count_positive 
        CHECK (char_count IS NULL OR char_count >= 0),
    
    -- 确保组件和文本块1:1关系
    UNIQUE (component_id)
);

-- ================================
-- 图片块子类表 (Photo Chunks)
-- ================================

-- 图片表（组件的图片子类）
CREATE TABLE IF NOT EXISTS unifiles.photos (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 图片块唯一标识
    
    -- 组件关联
    component_id TEXT NOT NULL,                            -- 组件ID（1:1关系）
    extracted_asset_id TEXT,                               -- 提取资源ID（引用，可为空）
    
    -- 图片基本属性
    photo_description TEXT,                                -- 图片描述
    alt_text TEXT,                                         -- 替代文本
    
    -- 图片类型
    photo_subtype TEXT DEFAULT 'image',                   -- 图片子类型
    
    -- 基本尺寸信息
    width INTEGER,                                         -- 宽度
    height INTEGER,                                        -- 高度
    file_size BIGINT,                                      -- 文件大小（字节，使用BIGINT支持大文件）
    format TEXT,                                           -- 文件格式
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_photos_component_id 
        FOREIGN KEY (component_id) REFERENCES unifiles.components(id) ON DELETE CASCADE,
    CONSTRAINT fk_photos_extracted_asset_id 
        FOREIGN KEY (extracted_asset_id) REFERENCES unifiles.extracted_assets(id) ON DELETE SET NULL,
    
    -- 检查约束
    CONSTRAINT chk_photos_subtype 
        CHECK (photo_subtype IN ('image', 'chart', 'diagram', 'table', 'formula', 'screenshot', 
                                'drawing', 'photo', 'icon', 'logo')),
    CONSTRAINT chk_photos_dimensions_positive 
        CHECK ((width IS NULL OR width > 0) AND (height IS NULL OR height > 0)),
    
    -- 确保组件和图片1:1关系
    UNIQUE (component_id)
);

-- ================================
-- 搜索优化函数和触发器
-- ================================

-- (已移除) 搜索字段的自动更新逻辑已移至应用层处理
-- 原有的 clean_text_for_search, detect_content_language, update_component_search_fields 函数及触发器已废弃


-- ================================
-- 向量维度管理函数 (Vector Dimension Management)  
-- ================================

-- 验证向量维度一致性的函数
CREATE OR REPLACE FUNCTION unifiles.validate_embedding_dimensions()
RETURNS TABLE(component_id TEXT, stored_dimensions INTEGER, actual_dimensions INTEGER) AS $$
BEGIN
  RETURN QUERY
  SELECT c.id,
         c.embedding_dimensions,
         CASE WHEN c.embedding IS NOT NULL THEN vector_dims(c.embedding) ELSE NULL END
  FROM unifiles.components c
  WHERE c.embedding IS NOT NULL
    AND c.embedding_dimensions IS NOT NULL
    AND c.embedding_dimensions <> vector_dims(c.embedding);
END;
$$ LANGUAGE plpgsql;


-- 获取向量维度统计的函数
CREATE OR REPLACE FUNCTION unifiles.get_embedding_dimension_stats()
RETURNS TABLE(dimensions INTEGER, count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.embedding_dimensions,
        COUNT(*) as count
    FROM unifiles.components c
    WHERE c.embedding IS NOT NULL 
      AND c.embedding_dimensions IS NOT NULL
    GROUP BY c.embedding_dimensions
    ORDER BY c.embedding_dimensions;
END;
$$ LANGUAGE plpgsql;

-- 创建向量索引的函数（需要有足够数据时调用）
CREATE OR REPLACE FUNCTION unifiles.create_embedding_index(lists_count INTEGER DEFAULT 100)
RETURNS TEXT AS $$
DECLARE
    data_count INTEGER;
    result_msg TEXT;
BEGIN
    -- 检查数据量
    SELECT COUNT(*) INTO data_count 
    FROM unifiles.components 
    WHERE embedding IS NOT NULL;
    
    -- 建议至少有1000条数据时再创建IVF索引
    IF data_count < 1000 THEN
        result_msg := format('警告：当前只有 %s 条向量数据，建议至少有1000条数据时再创建IVF索引以获得最佳性能', data_count);
    END IF;
    
    -- 删除现有索引
    DROP INDEX IF EXISTS unifiles.idx_components_embedding;
    
    -- 根据数据量选择索引类型
    IF data_count >= 1000 THEN
        -- 数据量足够，使用IVF索引
        EXECUTE format('CREATE INDEX idx_components_embedding ON unifiles.components USING ivfflat (embedding vector_cosine_ops) WITH (lists = %s) WHERE embedding IS NOT NULL', lists_count);
        result_msg := format('IVF向量索引创建成功，lists=%s，数据量=%s', lists_count, data_count);
    ELSE
        -- 数据量较少，使用简单的向量索引
        CREATE INDEX idx_components_embedding ON unifiles.components USING ivfflat (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
        result_msg := format('基础向量索引创建成功，数据量=%s（建议数据量达到1000+时重建IVF索引）', data_count);
    END IF;
    
    RETURN result_msg;
EXCEPTION
    WHEN OTHERS THEN
        RETURN format('向量索引创建失败: %s', SQLERRM);
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为components表添加更新时间戳触发器
CREATE TRIGGER trigger_components_updated_at
    BEFORE UPDATE ON unifiles.components
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为chunks表添加更新时间戳触发器
CREATE TRIGGER trigger_chunks_updated_at
    BEFORE UPDATE ON unifiles.chunks
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为photos表添加更新时间戳触发器
CREATE TRIGGER trigger_photos_updated_at
    BEFORE UPDATE ON unifiles.photos
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();
