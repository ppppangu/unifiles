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
-- 组件抽象表 (Component Abstraction)
-- ================================

-- 组件表（文档分块后的统一组件抽象）
CREATE TABLE IF NOT EXISTS chunk_schema.components (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 组件唯一标识
    
    -- 文档关联
    document_id TEXT NOT NULL,                             -- 知识库文档ID
    
    -- 组件基本信息
    component_type TEXT NOT NULL,                          -- 组件类型（chunk/photo）
    component_index INTEGER NOT NULL,                      -- 组件在文档中的序号
    
    -- 组件内容（统一字段）
    content TEXT,                                          -- 组件内容（文本或图片描述）
    
    -- 向量索引（统一）
    embedding vector,                                      -- 向量嵌入
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_components_document_id 
        FOREIGN KEY (document_id) REFERENCES chunk_schema.documents(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_components_type 
        CHECK (component_type IN ('chunk', 'photo')),
    CONSTRAINT chk_components_component_index_positive 
        CHECK (component_index >= 0),
    
    -- 确保组件在文档中的序号唯一
    UNIQUE (document_id, component_index)
);

-- ================================
-- 文本块子类表 (Text Chunks)
-- ================================

-- 文本块表（组件的文本子类）
CREATE TABLE IF NOT EXISTS chunk_schema.chunks (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 文本块唯一标识
    
    -- 组件关联
    component_id TEXT NOT NULL,                            -- 组件ID（1:1关系）
    
    -- 文本块核心属性
    text_content TEXT NOT NULL,                            -- 文本内容
    
    -- 文本统计
    char_count INTEGER,                                    -- 字符数
    word_count INTEGER,                                    -- 词数
    token_count INTEGER,                                   -- token数
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,    -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,    -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_chunks_component_id 
        FOREIGN KEY (component_id) REFERENCES chunk_schema.components(id) ON DELETE CASCADE,
    
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
CREATE TABLE IF NOT EXISTS chunk_schema.photos (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 图片块唯一标识
    
    -- 组件关联
    component_id TEXT NOT NULL,                            -- 组件ID（1:1关系）
    extracted_asset_id TEXT NOT NULL,                     -- 提取资源ID（引用）
    
    -- 图片基本属性
    photo_description TEXT,                                -- 图片描述
    alt_text TEXT,                                         -- 替代文本
    
    -- 图片类型
    photo_subtype TEXT DEFAULT 'image',                   -- 图片子类型
    
    -- 基本尺寸信息
    width INTEGER,                                         -- 宽度
    height INTEGER,                                        -- 高度
    file_size INTEGER,                                     -- 文件大小
    format TEXT,                                           -- 文件格式
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 外键约束
    CONSTRAINT fk_photos_component_id 
        FOREIGN KEY (component_id) REFERENCES chunk_schema.components(id) ON DELETE CASCADE,
    CONSTRAINT fk_photos_extracted_asset_id 
        FOREIGN KEY (extracted_asset_id) REFERENCES chunk_schema.extracted_assets(id) ON DELETE CASCADE,
    
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
-- 触发器 (Triggers)
-- ================================

-- 为components表添加更新时间戳触发器
CREATE TRIGGER trigger_components_updated_at
    BEFORE UPDATE ON chunk_schema.components
    FOR EACH ROW
    EXECUTE FUNCTION chunk_schema.update_updated_at_column();

-- 为chunks表添加更新时间戳触发器
CREATE TRIGGER trigger_chunks_updated_at
    BEFORE UPDATE ON chunk_schema.chunks
    FOR EACH ROW
    EXECUTE FUNCTION chunk_schema.update_updated_at_column();

-- 为photos表添加更新时间戳触发器
CREATE TRIGGER trigger_photos_updated_at
    BEFORE UPDATE ON chunk_schema.photos
    FOR EACH ROW
    EXECUTE FUNCTION chunk_schema.update_updated_at_column();