/*
 * 文件名: 041-create-content-extraction.sql
 * 作用: 创建优化后的内容处理层表结构
 * 分类: 内容处理层
 * 执行顺序: 第四步 - 在文件管理表创建后执行
 * 
 * 优化说明:
 * 1. processing_strategies表: 处理策略配置，管理处理器信息
 * 2. extracted_documents表: 存储处理后的完整文档内容
 * 3. extracted_assets表: 存储文档中提取的资源
 * 4. process_logs表: 统一的处理日志表，包含正常日志和错误日志
 * 
 * 设计原则:
 * - 策略配置独立管理，灵活支持多种处理方法
 * - 简化数据结构，移除冗余字段
 * - 强大的日志系统支持完整链路追踪
 * - 优化索引策略提高查询性能
 */

-- ================================
-- 处理策略配置表 (Processing Strategies)
-- ================================

-- 处理策略配置表
CREATE TABLE IF NOT EXISTS unifiles.processing_strategies (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 策略唯一标识
    
    -- 基本信息
    strategy_name TEXT NOT NULL,                           -- 策略名称（用于显示）
    strategy_type TEXT NOT NULL,                           -- 策略类型（ocr, nlp, multimodal）
    
    -- 处理器配置
    processing_config JSONB NOT NULL,                      -- 处理器配置（包含method、version、engine、parameters等）
    /*
     * processing_config 示例:
     * {
     *   "method": "mineru",                             -- 处理方法
     *   "deplo"
     *   "version": "1.0.0",                             -- 处理器版本
     *   "engine": "paddle-ocr-v3",                      -- OCR引擎
     *   "model": "gpt-vision-preview",                  -- 多模态模型
     *   "parameters": {                                 -- 处理参数
     *     "dpi": 300,
     *     "quality_settings": {
     *       "min_confidence": 0.7,
     *       "enhance_image": true
     *     }
     *   }
     * }
     */
    
    -- 元数据
    is_active BOOLEAN DEFAULT TRUE,                        -- 是否启用
    supported_formats TEXT[] DEFAULT '{}',                 -- 支持的文件格式
    
    -- 性能配置
    performance_config JSONB DEFAULT '{}',                 -- 性能配置（并发数、超时、内存限制等）
    /*
     * performance_config 示例:
     * {
     *   "max_concurrency": 5,
     *   "timeout_seconds": 300,
     *   "max_memory_mb": 2048,
     *   "batch_size": 10
     * }
     */
    
    -- 描述信息
    description TEXT,                                      -- 策略描述
    metadata JSONB DEFAULT '{}',                          -- 额外元数据
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 检查约束
    CONSTRAINT chk_processing_strategies_type 
        CHECK (strategy_type IN ('ocr', 'nlp', 'multimodal', 'hybrid', 'custom')),
    CONSTRAINT chk_processing_strategies_config_has_method
        CHECK (processing_config ? 'method'),
    CONSTRAINT chk_processing_strategies_config_has_version
        CHECK (processing_config ? 'version')
);

-- ================================
-- 提取文档表 (Extracted Documents)
-- ================================

-- 提取文档表（处理后的完整文档）
CREATE TABLE IF NOT EXISTS unifiles.extracted_documents (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 提取文档唯一标识
    
    -- 源文件关联
    file_id TEXT NOT NULL,                                 -- 源文件ID
    user_id TEXT NOT NULL,                                 -- 用户ID（冗余，便于查询）
    
    -- 策略关联
    extraction_strategy_id TEXT NOT NULL,                  -- 处理策略ID
    
    -- 存储配置关联
    storage_config_id TEXT,                                -- 存储配置ID（用于存储提取后的文档）
    storage_path TEXT,                                     -- 存储路径（相对路径）
    
    -- 核心内容
    full_markdown TEXT NOT NULL,                           -- 完整markdown文档
    
    -- 文档统计
    total_pages INTEGER DEFAULT 0,                         -- 总页数
    total_chars INTEGER DEFAULT 0,                         -- 总字符数
    total_assets INTEGER DEFAULT 0,                        -- 总资源数（图片、表格等）
    
    -- 处理状态（简化状态）
    extraction_status TEXT DEFAULT 'completed',            -- 提取状态
    
    -- 处理性能
    performance_metrics JSONB DEFAULT '{}',                -- 性能指标（通过process_logs聚合计算）
    /*
     * performance_metrics 示例（从process_logs聚合）:
     * {
     *   "total_duration_ms": 15000,
     *   "extraction_duration_ms": 10000,
     *   "post_processing_duration_ms": 5000,
     *   "memory_peak_mb": 512,
     *   "cpu_usage_percent": 45
     * }
     */
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    
    -- 外键约束
    CONSTRAINT fk_extracted_documents_strategy_id 
        FOREIGN KEY (extraction_strategy_id) REFERENCES unifiles.processing_strategies(id),
    CONSTRAINT fk_extracted_documents_storage_config_id 
        FOREIGN KEY (storage_config_id) REFERENCES unifiles.storage_configs(id) ON DELETE SET NULL,
    CONSTRAINT fk_extracted_documents_file_id 
        FOREIGN KEY (file_id) REFERENCES unifiles.files(id) ON DELETE CASCADE,
    
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
CREATE TABLE IF NOT EXISTS unifiles.extracted_assets (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 资源唯一标识
    
    -- 文档关联
    extracted_document_id TEXT NOT NULL,                   -- 提取文档ID
    
    -- 资源基本信息
    asset_type TEXT NOT NULL,                              -- 资源类型
    asset_subtype TEXT,                                    -- 资源子类型
    asset_name TEXT,                                       -- 资源名称
    original_filename TEXT,                                -- 原始文件名
    
    -- 存储信息
    storage_config_id TEXT,                                -- 存储配置ID（关联storage_configs表）
    storage_path TEXT NOT NULL,                           -- 存储路径（相对于配置的base_path）
    
    -- 文件属性
    file_size BIGINT,                                      -- 文件大小（字节）
    file_hash TEXT,                                        -- 文件哈希
    format TEXT,                                           -- 文件格式
    mime_type TEXT,                                        -- MIME类型
    
    -- 位置信息
    position_in_document INTEGER,                          -- 在文档中的位置序号
    page_number INTEGER,                                   -- 所在页码
    bounding_box JSONB,                                    -- 边界框信息
    
    -- 内容信息
    asset_description TEXT,                                -- 资源描述
    extracted_text TEXT,                                  -- 从资源中提取的文本（如表格文本）
    alt_text TEXT,                                         -- 替代文本
    caption TEXT,                                          -- 标题/说明
    
    -- 质量信息
    extraction_confidence FLOAT,                          -- 提取置信度（0-1）
    
    -- 资源元数据
    asset_metadata JSONB DEFAULT '{}',                    -- 资源详细元数据
    /*
     * asset_metadata 示例:
     * {
     *   "dimensions": {"width": 1920, "height": 1080},
     *   "resolution_dpi": 300,
     *   "color_mode": "RGB",
     *   "table_structure": {...},  -- 对于表格资源
     *   "quality_metrics": {        -- 质量相关指标
     *     "sharpness": 0.9,
     *     "contrast": 0.85
     *   }
     * }
     */
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    
    -- 外键约束
    CONSTRAINT fk_extracted_assets_document_id 
        FOREIGN KEY (extracted_document_id) REFERENCES unifiles.extracted_documents(id) ON DELETE CASCADE,
    CONSTRAINT fk_extracted_assets_storage_config_id 
        FOREIGN KEY (storage_config_id) REFERENCES unifiles.storage_configs(id) ON DELETE SET NULL,
    
    -- 检查约束
    CONSTRAINT chk_extracted_assets_type 
        CHECK (asset_type IN ('text', 'image', 'table', 'code', 'chart', 'formula')),
    CONSTRAINT chk_extracted_assets_confidence 
        CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)),
    CONSTRAINT chk_extracted_assets_file_size_positive 
        CHECK (file_size IS NULL OR file_size >= 0)
);

-- ================================
-- 处理日志表 (Process Logs) - 统一日志和错误记录
-- ================================

-- 统一的处理日志表（包含正常日志和错误日志）
CREATE TABLE IF NOT EXISTS unifiles.process_logs (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 日志唯一标识
    
    -- 日志类型和级别
    log_type TEXT NOT NULL,                                -- 日志类型（log, error）
    log_level TEXT DEFAULT 'info',                         -- 日志级别（debug, info, warning, error, critical）
    
    -- 处理类型和阶段
    process_type TEXT NOT NULL,                            -- 处理类型
    process_stage TEXT,                                    -- 处理阶段（更细粒度的步骤）
    process_id TEXT,                                       -- 处理批次ID（用于关联同一批处理）
    parent_process_id TEXT,                               -- 父处理ID（用于嵌套处理链路）
    
    -- 关联对象（根据process_type动态使用）
    entity_type TEXT,                                      -- 实体类型（file, document, asset, chunk等）
    entity_id TEXT,                                        -- 实体ID
    user_id TEXT,                                          -- 用户ID（如果相关）
    
    -- 处理信息
    action TEXT NOT NULL,                                  -- 执行的动作
    status TEXT NOT NULL,                                  -- 状态（started, completed, failed）
    
    -- 消息和错误信息
    message TEXT,                                          -- 日志消息或错误消息
    error_code TEXT,                                       -- 错误代码（错误日志时使用）
    error_details JSONB DEFAULT '{}',                      -- 错误详情（错误日志时使用）
    stack_trace TEXT,                                      -- 堆栈跟踪（错误日志时使用）
    
    -- 输入输出信息
    input_params JSONB DEFAULT '{}',                      -- 输入参数
    output_results JSONB DEFAULT '{}',                    -- 输出结果
    
    -- 性能指标
    start_time TIMESTAMPTZ,                               -- 开始时间
    end_time TIMESTAMPTZ,                                 -- 结束时间
    duration_ms INTEGER,                                  -- 持续时间（毫秒）
    resource_usage JSONB DEFAULT '{}',                    -- 资源使用情况
    
    -- 质量指标
    quality_metrics JSONB DEFAULT '{}',                   -- 质量指标
    
    -- 策略信息
    strategy_id TEXT,                                     -- 使用的策略ID
    strategy_config JSONB DEFAULT '{}',                   -- 策略配置快照
    
    -- 链路追踪信息
    trace_id TEXT,                                        -- 分布式追踪ID（用于跨服务追踪）
    span_id TEXT,                                         -- 跨度ID（用于分布式追踪）
    
    -- 元数据
    metadata JSONB DEFAULT '{}',                          -- 额外元数据
    context_info JSONB DEFAULT '{}',                      -- 上下文信息（环境变量、系统状态等）
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    
    -- 检查约束
    CONSTRAINT chk_process_logs_log_type 
        CHECK (log_type IN ('log', 'error')),
    CONSTRAINT chk_process_logs_log_level 
        CHECK (log_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_process_logs_type 
        CHECK (process_type IN ('extraction', 'chunking', 'embedding', 'fine_tuning', 
                               'validation', 'storage', 'indexing', 'migration', 'preprocessing',
                               'postprocessing', 'quality_check', 'optimization')),
    CONSTRAINT chk_process_logs_status 
        CHECK (status IN ('started', 'in_progress', 'completed', 'failed', 'cancelled', 'retrying')),
    CONSTRAINT chk_process_logs_entity_type
        CHECK (entity_type IN ('file', 'document', 'asset', 'chunk', 'embedding', 
                              'knowledge_base', 'user', 'batch', 'pipeline'))
);

-- ================================
-- 索引优化
-- ================================

-- processing_strategies表索引
CREATE INDEX idx_processing_strategies_active 
    ON unifiles.processing_strategies(is_active) 
    WHERE is_active = TRUE;
CREATE INDEX idx_processing_strategies_type 
    ON unifiles.processing_strategies(strategy_type);
CREATE INDEX idx_processing_strategies_type_active 
    ON unifiles.processing_strategies(strategy_type, is_active) 
    WHERE is_active = TRUE;

-- extracted_documents表索引
CREATE INDEX idx_extracted_documents_file_id 
    ON unifiles.extracted_documents(file_id);
CREATE INDEX idx_extracted_documents_user_id 
    ON unifiles.extracted_documents(user_id);
CREATE INDEX idx_extracted_documents_strategy_id 
    ON unifiles.extracted_documents(extraction_strategy_id);
CREATE INDEX idx_extracted_documents_status 
    ON unifiles.extracted_documents(extraction_status) 
    WHERE extraction_status != 'completed';
CREATE INDEX idx_extracted_documents_created_at 
    ON unifiles.extracted_documents(created_at DESC);
-- 复合索引用于常见查询模式
CREATE INDEX idx_extracted_documents_user_status 
    ON unifiles.extracted_documents(user_id, extraction_status, created_at DESC);

-- extracted_assets表索引
CREATE INDEX idx_extracted_assets_document_id 
    ON unifiles.extracted_assets(extracted_document_id);
CREATE INDEX idx_extracted_assets_type 
    ON unifiles.extracted_assets(asset_type);
CREATE INDEX idx_extracted_assets_storage_config 
    ON unifiles.extracted_assets(storage_config_id) 
    WHERE storage_config_id IS NOT NULL;
CREATE INDEX idx_extracted_assets_position 
    ON unifiles.extracted_assets(extracted_document_id, position_in_document);
CREATE INDEX idx_extracted_assets_page 
    ON unifiles.extracted_assets(extracted_document_id, page_number) 
    WHERE page_number IS NOT NULL;
-- 用于资源检索的复合索引
CREATE INDEX idx_extracted_assets_doc_type_page 
    ON unifiles.extracted_assets(extracted_document_id, asset_type, page_number);

-- process_logs表索引（优化链路追踪查询）
CREATE INDEX idx_process_logs_type 
    ON unifiles.process_logs(process_type);
CREATE INDEX idx_process_logs_process_id 
    ON unifiles.process_logs(process_id);
CREATE INDEX idx_process_logs_parent_id 
    ON unifiles.process_logs(parent_process_id) 
    WHERE parent_process_id IS NOT NULL;
CREATE INDEX idx_process_logs_entity 
    ON unifiles.process_logs(entity_type, entity_id);
CREATE INDEX idx_process_logs_status 
    ON unifiles.process_logs(status) 
    WHERE status IN ('failed', 'cancelled');
CREATE INDEX idx_process_logs_created_at 
    ON unifiles.process_logs(created_at DESC);
CREATE INDEX idx_process_logs_trace 
    ON unifiles.process_logs(trace_id, span_id) 
    WHERE trace_id IS NOT NULL;
-- 复合索引用于链路查询
CREATE INDEX idx_process_logs_chain 
    ON unifiles.process_logs(process_id, created_at, status);
CREATE INDEX idx_process_logs_entity_chain 
    ON unifiles.process_logs(entity_id, entity_type, created_at DESC);

-- process_logs表索引（包含日志和错误类型）
CREATE INDEX idx_process_logs_log_type ON unifiles.process_logs(log_type);
CREATE INDEX idx_process_logs_log_level ON unifiles.process_logs(log_level);
CREATE INDEX idx_process_logs_error_logs ON unifiles.process_logs(log_type, log_level, created_at DESC) 
    WHERE log_type = 'error';
CREATE INDEX idx_process_logs_user_id ON unifiles.process_logs(user_id) 
    WHERE user_id IS NOT NULL;

-- ================================
-- 触发器函数
-- ================================

-- 自动更新updated_at时间戳
-- Removed duplicate function by patch


-- 为processing_strategies表创建触发器
CREATE TRIGGER update_processing_strategies_updated_at 
    BEFORE UPDATE ON unifiles.processing_strategies
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 自动计算处理时长
CREATE OR REPLACE FUNCTION unifiles.calculate_duration_ms()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.end_time IS NOT NULL AND NEW.start_time IS NOT NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为process_logs表创建触发器
CREATE TRIGGER calculate_process_logs_duration 
    BEFORE INSERT OR UPDATE ON unifiles.process_logs
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.calculate_duration_ms();

-- 自动聚合性能指标到extracted_documents
CREATE OR REPLACE FUNCTION unifiles.update_document_performance_metrics()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entity_type = 'document' AND NEW.status = 'completed' THEN
        UPDATE unifiles.extracted_documents
        SET performance_metrics = (
            SELECT jsonb_build_object(
                'total_duration_ms', SUM(duration_ms),
                'stages_count', COUNT(DISTINCT process_stage),
                'last_updated', CURRENT_TIMESTAMP
            )
            FROM unifiles.process_logs
            WHERE entity_id = NEW.entity_id
                AND entity_type = 'document'
                AND status = 'completed'
        )
        WHERE id = NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器更新文档性能指标
CREATE TRIGGER update_document_metrics_on_log 
    AFTER INSERT OR UPDATE ON unifiles.process_logs
    FOR EACH ROW
    WHEN (NEW.entity_type = 'document' AND NEW.status = 'completed')
    EXECUTE FUNCTION unifiles.update_document_performance_metrics();

-- ================================
-- 物化视图（用于性能优化）
-- ================================

-- 创建处理链路视图（用于快速查询完整处理链路）
CREATE MATERIALIZED VIEW IF NOT EXISTS unifiles.mv_processing_chains AS
SELECT 
    pl.process_id,
    pl.entity_id,
    pl.entity_type,
    MIN(pl.start_time) as chain_start_time,
    MAX(pl.end_time) as chain_end_time,
    SUM(pl.duration_ms) as total_duration_ms,
    COUNT(*) as stages_count,
    jsonb_agg(
        jsonb_build_object(
            'stage', pl.process_stage,
            'type', pl.process_type,
            'status', pl.status,
            'duration_ms', pl.duration_ms
        ) ORDER BY pl.created_at
    ) as stages
FROM unifiles.process_logs pl
GROUP BY pl.process_id, pl.entity_id, pl.entity_type;

-- 创建索引加速物化视图查询
CREATE INDEX idx_mv_processing_chains_entity 
    ON unifiles.mv_processing_chains(entity_id, entity_type);
CREATE INDEX idx_mv_processing_chains_process 
    ON unifiles.mv_processing_chains(process_id);

-- ================================
-- 注释说明
-- ================================

-- processing_strategies表注释
COMMENT ON TABLE unifiles.processing_strategies IS '处理策略配置表，管理不同的处理方法和版本';
COMMENT ON COLUMN unifiles.processing_strategies.processing_config IS '处理器配置，包含method、version、engine、parameters等信息';
COMMENT ON COLUMN unifiles.processing_strategies.performance_config IS '性能配置，包含并发数、超时、内存限制等';

-- extracted_documents表注释
COMMENT ON TABLE unifiles.extracted_documents IS '提取文档表，存储处理后的完整文档内容';
COMMENT ON COLUMN unifiles.extracted_documents.extraction_strategy_id IS '引用处理策略配置';
COMMENT ON COLUMN unifiles.extracted_documents.performance_metrics IS '性能指标，从process_logs聚合计算';

-- extracted_assets表注释
COMMENT ON TABLE unifiles.extracted_assets IS '提取资源表，存储文档中的图片、表格等资源';
COMMENT ON COLUMN unifiles.extracted_assets.asset_metadata IS '资源元数据，包含尺寸、分辨率、质量指标等';

-- process_logs表注释
COMMENT ON TABLE unifiles.process_logs IS '统一的处理日志表，支持完整的处理链路追踪';
COMMENT ON COLUMN unifiles.process_logs.process_type IS '处理类型：extraction, chunking, embedding等';
COMMENT ON COLUMN unifiles.process_logs.parent_process_id IS '父处理ID，用于构建处理链路树';
COMMENT ON COLUMN unifiles.process_logs.trace_id IS '分布式追踪ID，用于跨服务追踪';
COMMENT ON COLUMN unifiles.process_logs.span_id IS '跨度ID，用于分布式追踪中的具体操作标识';

-- process_logs表注释补充
COMMENT ON COLUMN unifiles.process_logs.log_type IS '日志类型：log为正常日志，error为错误日志';
COMMENT ON COLUMN unifiles.process_logs.log_level IS '日志级别，error类型时表示错误严重程度';

-- ================================
-- 辅助函数（用于链路查询）
-- ================================

-- 获取完整处理链路
CREATE OR REPLACE FUNCTION unifiles.get_processing_chain(p_entity_id TEXT)
RETURNS TABLE (
    log_id TEXT,
    process_type TEXT,
    process_stage TEXT,
    status TEXT,
    start_time TIMESTAMPTZ,
    duration_ms INTEGER,
    level INTEGER
) AS $$
WITH RECURSIVE chain AS (
    -- 基础查询：找到根节点
    SELECT 
        id,
        process_type,
        process_stage,
        status,
        start_time,
        duration_ms,
        process_id,
        parent_process_id,
        0 as level
    FROM unifiles.process_logs
    WHERE entity_id = p_entity_id
        AND parent_process_id IS NULL
    
    UNION ALL
    
    -- 递归查询：找到所有子节点
    SELECT 
        pl.id,
        pl.process_type,
        pl.process_stage,
        pl.status,
        pl.start_time,
        pl.duration_ms,
        pl.process_id,
        pl.parent_process_id,
        c.level + 1
    FROM unifiles.process_logs pl
    INNER JOIN chain c ON pl.parent_process_id = c.process_id
)
SELECT 
    id as log_id,
    process_type,
    process_stage,
    status,
    start_time,
    duration_ms,
    level
FROM chain
ORDER BY start_time, level;
$$ LANGUAGE SQL;

-- 获取处理链路统计
CREATE OR REPLACE FUNCTION unifiles.get_processing_stats(
    p_start_date TIMESTAMPTZ DEFAULT CURRENT_DATE - INTERVAL '7 days',
    p_end_date TIMESTAMPTZ DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    process_type TEXT,
    total_count BIGINT,
    success_count BIGINT,
    failure_count BIGINT,
    avg_duration_ms NUMERIC,
    success_rate NUMERIC
) AS $$
SELECT 
    process_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE status = 'completed') as success_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failure_count,
    ROUND(AVG(duration_ms), 2) as avg_duration_ms,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC / 
        NULLIF(COUNT(*), 0) * 100, 
        2
    ) as success_rate
FROM unifiles.process_logs
WHERE created_at BETWEEN p_start_date AND p_end_date
GROUP BY process_type
ORDER BY total_count DESC;
$$ LANGUAGE SQL;