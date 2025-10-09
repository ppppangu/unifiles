/*
 * 文件名: 081-create-triggers.sql
 * 作用: 创建触发器和自动化逻辑
 * 分类: 触发器和自动化
 * 执行顺序: 第八步 - 在所有表和索引创建后执行
 * 
 * 功能说明:
 * 1. 数据同步触发器: 维护统计数据和关联关系的一致性
 * 2. 全文搜索触发器: 自动更新搜索向量和索引
 * 3. 审计触发器: 记录重要数据变更
 * 4. 业务逻辑触发器: 实现自动化的业务规则
 * 5. 缓存更新触发器: 维护缓存数据的一致性
 * 
 * 设计原则:
 * - 最小化触发器复杂度，避免性能影响
 * - 使用条件触发，只在必要时执行
 * - 错误处理和日志记录
 * - 支持触发器的启用和禁用
 */

-- ================================
-- 工具函数 (Utility Functions)
-- ================================

-- 生成UUID函数
CREATE OR REPLACE FUNCTION unifiles.generate_uuid() 
RETURNS TEXT AS $$
BEGIN
    RETURN gen_random_uuid()::TEXT;
END;
$$ LANGUAGE plpgsql;

-- 更新统计信息函数
CREATE OR REPLACE FUNCTION unifiles.update_statistics(
    table_name TEXT,
    record_id TEXT,
    operation TEXT,
    delta_value INTEGER DEFAULT 1
) 
RETURNS VOID AS $$
BEGIN
    -- 这里可以实现统计更新逻辑
    -- 为了简化，现在只是一个占位符
    -- 实际使用时可以根据需要扩展
    NULL;
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 云端存储URL生成函数 (Cloud Storage URL Functions)
-- ================================

-- 根据存储配置生成URL的函数（修正版本，基于实际表结构）
CREATE OR REPLACE FUNCTION unifiles.generate_storage_urls(
    storage_config_id_param TEXT,
    storage_path_param TEXT
) 
RETURNS TABLE (
    public_url TEXT
) AS $$
DECLARE
    config_rec RECORD;
    generated_public_url TEXT;
BEGIN
    -- 如果没有配置ID，使用第一个活跃的配置
    -- 建议在应用层指定具体的storage_config_id
    IF storage_config_id_param IS NULL THEN
        SELECT * INTO config_rec
        FROM unifiles.storage_configs
        WHERE is_active = true
        ORDER BY created_at ASC
        LIMIT 1;
    ELSE
        SELECT * INTO config_rec
        FROM unifiles.storage_configs
        WHERE id = storage_config_id_param AND is_active = true;
    END IF;
    
    -- 如果找不到配置，返回NULL
    IF config_rec IS NULL THEN
        public_url := NULL;
        RETURN NEXT;
        RETURN;
    END IF;
    
    -- 根据存储配置生成公共访问URL
    IF config_rec.public_url_prefix IS NOT NULL AND storage_path_param IS NOT NULL THEN
        generated_public_url := config_rec.public_url_prefix || '/' || LTRIM(storage_path_param, '/');
    ELSIF config_rec.endpoint IS NOT NULL AND config_rec.bucket_name IS NOT NULL AND storage_path_param IS NOT NULL THEN
        generated_public_url := config_rec.endpoint || '/' || config_rec.bucket_name || '/' || LTRIM(storage_path_param, '/');
    END IF;
    
    public_url := generated_public_url;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ================================
-- 文本搜索向量更新触发器 (Full-Text Search Triggers)
-- ================================

-- 已经简化了组件表，移除了search_vector字段和相关触发器
-- 现在使用简单的全文搜索索引

-- ================================
-- 统计数据同步触发器 (Statistics Sync Triggers)
-- ================================

-- 更新知识库统计信息的函数（基于简化后的结构）
CREATE OR REPLACE FUNCTION unifiles.update_knowledge_base_stats()
RETURNS TRIGGER AS $$
DECLARE
    kb_id TEXT;
    doc_count INTEGER;
    comp_count INTEGER;
    chunk_count INTEGER;
    photo_count INTEGER;
BEGIN
    -- 确定要更新的知识库ID
    IF TG_OP = 'DELETE' THEN
        kb_id := OLD.knowledge_base_id;
    ELSE
        kb_id := NEW.knowledge_base_id;
    END IF;
    
    -- 计算统计数据
    SELECT COUNT(*) INTO doc_count 
    FROM unifiles.documents 
    WHERE knowledge_base_id = kb_id;
    
    SELECT COUNT(*) INTO comp_count
    FROM unifiles.components c
    INNER JOIN unifiles.documents d ON c.document_id = d.id
    WHERE d.knowledge_base_id = kb_id;
    
    SELECT COUNT(*) INTO chunk_count
    FROM unifiles.components c
    INNER JOIN unifiles.documents d ON c.document_id = d.id
    WHERE d.knowledge_base_id = kb_id AND c.component_type = 'chunk';
    
    SELECT COUNT(*) INTO photo_count
    FROM unifiles.components c
    INNER JOIN unifiles.documents d ON c.document_id = d.id
    WHERE d.knowledge_base_id = kb_id AND c.component_type = 'photo';
    
    -- 更新知识库的document_ids字段（保留基本统计信息）
    UPDATE unifiles.knowledge_bases 
    SET 
        updated_at = CURRENT_TIMESTAMP
    WHERE id = kb_id;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 为文档表添加知识库统计更新触发器
CREATE TRIGGER trigger_documents_update_kb_stats
    AFTER INSERT OR UPDATE OR DELETE ON unifiles.documents
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_knowledge_base_stats();

-- 更新文档统计信息的函数（基于简化后的结构）
CREATE OR REPLACE FUNCTION unifiles.update_document_stats()
RETURNS TRIGGER AS $$
DECLARE
    doc_id TEXT;
    comp_count INTEGER;
    chunk_count INTEGER;
    photo_count INTEGER;
BEGIN
    -- 确定要更新的文档ID
    IF TG_OP = 'DELETE' THEN
        doc_id := OLD.document_id;
    ELSE
        doc_id := NEW.document_id;
    END IF;
    
    -- 计算统计数据
    SELECT COUNT(*) INTO comp_count
    FROM unifiles.components
    WHERE document_id = doc_id;
    
    SELECT COUNT(*) INTO chunk_count
    FROM unifiles.components
    WHERE document_id = doc_id AND component_type = 'chunk';
    
    SELECT COUNT(*) INTO photo_count
    FROM unifiles.components
    WHERE document_id = doc_id AND component_type = 'photo';
    
    -- 更新文档统计（对于简化后的文档表，只更新updated_at）
    UPDATE unifiles.documents 
    SET 
        updated_at = CURRENT_TIMESTAMP
    WHERE id = doc_id;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 为组件表添加文档统计更新触发器
CREATE TRIGGER trigger_components_update_doc_stats
    AFTER INSERT OR UPDATE OR DELETE ON unifiles.components
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_document_stats();

-- ================================
-- 文件统计同步触发器 (File Statistics Triggers)
-- ================================

-- 文件统计表已被移除，无需同步触发器

-- ================================
-- 审计日志触发器 (Audit Log Triggers)
-- ================================

-- 记录用户活动的函数
CREATE OR REPLACE FUNCTION unifiles.log_user_activity()
RETURNS TRIGGER AS $$
DECLARE
    action_desc TEXT;
    resource_type_val TEXT;
    resource_id_val TEXT;
    user_id_val TEXT;
BEGIN
    -- 确定操作描述和资源信息
    IF TG_TABLE_NAME = 'knowledge_bases' THEN
        resource_type_val := 'knowledge_base';
        IF TG_OP = 'INSERT' THEN
            action_desc := 'Created knowledge base: ' || NEW.name;
            resource_id_val := NEW.id;
            user_id_val := NEW.user_id;
        ELSIF TG_OP = 'UPDATE' THEN
            action_desc := 'Updated knowledge base: ' || NEW.name;
            resource_id_val := NEW.id;
            user_id_val := NEW.user_id;
        ELSIF TG_OP = 'DELETE' THEN
            action_desc := 'Deleted knowledge base: ' || OLD.name;
            resource_id_val := OLD.id;
            user_id_val := OLD.user_id;
        END IF;
    ELSIF TG_TABLE_NAME = 'documents' THEN
        resource_type_val := 'document';
        IF TG_OP = 'INSERT' THEN
            action_desc := 'Added document: ' || COALESCE(NEW.title, 'Untitled');
            resource_id_val := NEW.id;
            -- 需要通过知识库获取用户ID
            SELECT user_id INTO user_id_val 
            FROM unifiles.knowledge_bases 
            WHERE id = NEW.knowledge_base_id;
        ELSIF TG_OP = 'DELETE' THEN
            action_desc := 'Removed document: ' || COALESCE(OLD.title, 'Untitled');
            resource_id_val := OLD.id;
            SELECT user_id INTO user_id_val 
            FROM unifiles.knowledge_bases 
            WHERE id = OLD.knowledge_base_id;
        END IF;
    ELSIF TG_TABLE_NAME = 'files' THEN
        resource_type_val := 'file';
        IF TG_OP = 'INSERT' THEN
            action_desc := 'Uploaded file: ' || NEW.filename;
            resource_id_val := NEW.id;
            user_id_val := NEW.user_id;
        ELSIF TG_OP = 'UPDATE' AND OLD.status != NEW.status THEN
            action_desc := 'File status changed from ' || OLD.status || ' to ' || NEW.status || ': ' || NEW.filename;
            resource_id_val := NEW.id;
            user_id_val := NEW.user_id;
        ELSIF TG_OP = 'DELETE' THEN
            action_desc := 'Deleted file: ' || OLD.filename;
            resource_id_val := OLD.id;
            user_id_val := OLD.user_id;
        END IF;
    END IF;
    
    -- 用户活动日志表已被移除，无法记录活动日志
    -- 如果需要，可以在应用层记录日志
    IF action_desc IS NOT NULL AND user_id_val IS NOT NULL THEN
        RAISE NOTICE 'Activity: %', action_desc;
    END IF;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 由于没有用户活动日志表，暂时禁用活动日志触发器
-- 如果需要记录活动，建议在应用层处理
/*
CREATE TRIGGER trigger_knowledge_bases_activity_log
    AFTER INSERT OR UPDATE OR DELETE ON unifiles.knowledge_bases
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.log_user_activity();

CREATE TRIGGER trigger_documents_activity_log
    AFTER INSERT OR DELETE ON unifiles.documents
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.log_user_activity();

CREATE TRIGGER trigger_files_activity_log
    AFTER INSERT OR UPDATE OR DELETE ON unifiles.files
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.log_user_activity();
*/

-- ================================
-- 云端存储URL自动生成触发器 (Cloud Storage URL Generation Triggers)
-- ================================

-- 文件URL自动生成和更新函数（基于实际表结构）
CREATE OR REPLACE FUNCTION unifiles.update_file_urls()
RETURNS TRIGGER AS $$
BEGIN
    -- 由于files表中没有URL相关字段，此触发器保持为占位符
    -- 如果需要URL生成功能，可以在应用层处理或扩展表结构
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为files表添加URL自动生成触发器
CREATE TRIGGER trigger_files_update_urls
    BEFORE INSERT OR UPDATE ON unifiles.files
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_file_urls();

-- 提取资源URL自动生成和更新函数（基于实际表结构）
CREATE OR REPLACE FUNCTION unifiles.update_asset_urls()
RETURNS TRIGGER AS $$
BEGIN
    -- 由于extracted_assets表中没有URL相关字段，此触发器保持为占位符
    -- 如果需要URL生成功能，可以在应用层处理或扩展表结构
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为extracted_assets表添加URL自动生成触发器
CREATE TRIGGER trigger_assets_update_urls
    BEFORE INSERT OR UPDATE ON unifiles.extracted_assets
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_asset_urls();

-- 存储配置变更时更新相关文件URL的函数（基于实际表结构）
CREATE OR REPLACE FUNCTION unifiles.update_files_on_config_change()
RETURNS TRIGGER AS $$
BEGIN
    -- 当存储配置的关键信息发生变化时，更新相关文件的时间戳
    IF TG_OP = 'UPDATE' AND (
        OLD.endpoint IS DISTINCT FROM NEW.endpoint OR
        OLD.bucket_name IS DISTINCT FROM NEW.bucket_name OR
        OLD.base_path IS DISTINCT FROM NEW.base_path OR
        OLD.public_url_prefix IS DISTINCT FROM NEW.public_url_prefix OR
        OLD.is_active IS DISTINCT FROM NEW.is_active
    ) THEN
        -- 更新files表中使用此配置的记录
        UPDATE unifiles.files 
        SET updated_at = CURRENT_TIMESTAMP
        WHERE storage_config_id = NEW.id;
        
        -- 更新extracted_assets表中使用此配置的记录
        UPDATE unifiles.extracted_assets 
        SET created_at = created_at  -- 触发相关处理但不改变时间戳
        WHERE storage_config_id = NEW.id;
        
        RAISE NOTICE 'Updated files and assets using storage config: %', NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为storage_configs表添加配置变更触发器
CREATE TRIGGER trigger_storage_configs_update_urls
    AFTER UPDATE ON unifiles.storage_configs
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_files_on_config_change();

-- ================================
-- 数据完整性维护触发器 (Data Integrity Triggers)
-- ================================

-- 维护文档ID列表的函数
CREATE OR REPLACE FUNCTION unifiles.maintain_document_ids()
RETURNS TRIGGER AS $$
DECLARE
    kb_id TEXT;
    doc_ids TEXT[];
BEGIN
    -- 确定要更新的知识库ID
    IF TG_OP = 'DELETE' THEN
        kb_id := OLD.knowledge_base_id;
    ELSE
        kb_id := NEW.knowledge_base_id;
    END IF;
    
    -- 获取当前知识库的所有文档ID
    SELECT array_agg(id ORDER BY created_at) INTO doc_ids
    FROM unifiles.documents
    WHERE knowledge_base_id = kb_id;
    
    -- 更新知识库的文档ID列表
    UPDATE unifiles.knowledge_bases
    SET 
        document_ids = COALESCE(doc_ids, '{}'),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = kb_id;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 为文档表添加文档ID列表维护触发器
CREATE TRIGGER trigger_documents_maintain_ids
    AFTER INSERT OR DELETE ON unifiles.documents
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.maintain_document_ids();

-- ================================
-- 缓存无效化触发器 (Cache Invalidation Triggers)
-- ================================

-- 缓存无效化函数
CREATE OR REPLACE FUNCTION unifiles.invalidate_cache()
RETURNS TRIGGER AS $$
BEGIN
    -- 这里可以实现缓存无效化逻辑
    -- 例如：通知应用程序缓存需要更新
    -- 或者删除Redis中的相关缓存键
    
    -- 为了演示，我们只是记录一个简单的日志
    RAISE NOTICE 'Cache invalidation needed for table: %, operation: %', TG_TABLE_NAME, TG_OP;
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 为关键表添加缓存无效化触发器
CREATE TRIGGER trigger_components_cache_invalidation
    AFTER INSERT OR UPDATE OR DELETE ON unifiles.components
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.invalidate_cache();

-- ================================
-- 组件链关系维护触发器 (Component Chain Triggers)
-- ================================

-- 维护文本块链关系的函数（已移除，因为chunks表中没有链关系字段）
-- 如果需要维护文本块之间的顺序关系，可以通过component_index字段查询
-- 或者扩展chunks表结构添加previous_chunk_id和next_chunk_id字段

-- 占位符函数，避免触发器引用错误
CREATE OR REPLACE FUNCTION unifiles.maintain_chunk_chain()
RETURNS TRIGGER AS $$
BEGIN
    -- 此功能已禁用，因为chunks表中没有链关系字段
    -- 文本块的顺序可以通过components.component_index字段确定
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 暂时禁用此触发器，因为相关字段不存在
-- CREATE TRIGGER trigger_chunks_maintain_chain
--     AFTER INSERT ON unifiles.chunks
--     FOR EACH ROW
--     EXECUTE FUNCTION unifiles.maintain_chunk_chain();

-- ================================
-- 触发器管理函数 (Trigger Management Functions)
-- ================================

-- 禁用所有统计触发器的函数（用于批量数据操作）
CREATE OR REPLACE FUNCTION unifiles.disable_stats_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE unifiles.documents DISABLE TRIGGER trigger_documents_update_kb_stats;
    ALTER TABLE unifiles.components DISABLE TRIGGER trigger_components_update_doc_stats;
    -- 文件统计同步触发器已被移除
    RAISE NOTICE 'Statistics triggers disabled';
END;
$$ LANGUAGE plpgsql;

-- 启用所有统计触发器的函数
CREATE OR REPLACE FUNCTION unifiles.enable_stats_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE unifiles.documents ENABLE TRIGGER trigger_documents_update_kb_stats;
    ALTER TABLE unifiles.components ENABLE TRIGGER trigger_components_update_doc_stats;
    -- 文件统计同步触发器已被移除
    RAISE NOTICE 'Statistics triggers enabled';
END;
$$ LANGUAGE plpgsql;

-- 禁用URL生成触发器的函数（用于批量数据迁移）
CREATE OR REPLACE FUNCTION unifiles.disable_url_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE unifiles.files DISABLE TRIGGER trigger_files_update_urls;
    ALTER TABLE unifiles.extracted_assets DISABLE TRIGGER trigger_assets_update_urls;
    ALTER TABLE unifiles.storage_configs DISABLE TRIGGER trigger_storage_configs_update_urls;
    RAISE NOTICE 'URL generation triggers disabled';
END;
$$ LANGUAGE plpgsql;

-- 启用URL生成触发器的函数
CREATE OR REPLACE FUNCTION unifiles.enable_url_triggers()
RETURNS VOID AS $$
BEGIN
    ALTER TABLE unifiles.files ENABLE TRIGGER trigger_files_update_urls;
    ALTER TABLE unifiles.extracted_assets ENABLE TRIGGER trigger_assets_update_urls;
    ALTER TABLE unifiles.storage_configs ENABLE TRIGGER trigger_storage_configs_update_urls;
    RAISE NOTICE 'URL generation triggers enabled';
END;
$$ LANGUAGE plpgsql;

-- 批量更新文件URL的函数（用于存储迁移）
CREATE OR REPLACE FUNCTION unifiles.batch_update_file_urls(
    storage_config_id_param TEXT DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    updated_files_count INTEGER := 0;
    updated_assets_count INTEGER := 0;
BEGIN
    -- 禁用URL触发器以避免递归调用
    PERFORM unifiles.disable_url_triggers();
    
    -- 更新files表
    UPDATE unifiles.files 
    SET updated_at = CURRENT_TIMESTAMP
    WHERE (storage_config_id_param IS NULL OR storage_config_id = storage_config_id_param);
    
    GET DIAGNOSTICS updated_files_count = ROW_COUNT;
    
    -- 更新extracted_assets表
    UPDATE unifiles.extracted_assets 
    SET created_at = created_at  -- 触发URL更新但不改变时间戳
    WHERE (storage_config_id_param IS NULL OR storage_config_id = storage_config_id_param);
    
    GET DIAGNOSTICS updated_assets_count = ROW_COUNT;
    
    -- 重新启用URL触发器
    PERFORM unifiles.enable_url_triggers();
    
    RAISE NOTICE 'Batch updated URLs: % files, % assets', updated_files_count, updated_assets_count;
    
    RETURN updated_files_count + updated_assets_count;
END;
$$ LANGUAGE plpgsql;

-- 审计触发器已被禁用，无需管理函数
-- 如果需要，可以在应用层实现审计日志

-- ================================
-- 触发器状态监控视图 (Trigger Status Views)
-- ================================

-- 创建触发器状态监控视图
CREATE OR REPLACE VIEW unifiles.trigger_status AS
SELECT 
    n.nspname AS schemaname,
    c.relname AS tablename,
    t.tgname AS triggername,
    t.tgtype,
    t.tgenabled,
    CASE t.tgenabled
        WHEN 'O' THEN 'ENABLED'
        WHEN 'D' THEN 'DISABLED'
        WHEN 'R' THEN 'REPLICA_ONLY'
        WHEN 'A' THEN 'ALWAYS'
        ELSE 'UNKNOWN'
    END as status
FROM pg_trigger t
INNER JOIN pg_class c ON t.tgrelid = c.oid
INNER JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = 'unifiles'
AND NOT t.tgisinternal
ORDER BY n.nspname, c.relname, t.tgname;
