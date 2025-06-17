/*
 * 文件名: 022-create-chunk-trigger-index.sql
 * 作用: 创建表之间的关联触发器，实现数据自动同步
 * 组成:
 * 1. 用户-知识库关联触发器:
 *    - update_user_knowledge_uuids: 在知识库变更时自动更新用户的knowledge_ids
 * 2. 知识库-文档关联触发器:
 *    - update_knowledge_base_document_ids: 在文档变更时自动更新知识库的document_ids
 * 3. 文档内容排序触发器:
 *    - ensure_doc_position_uniqueness: 确保components的doc_position不重复
 * 4. 文档内容更新触发器:
 *    - update_document_content: 在components变更时更新文档的text和component_ids
 * 5. 组件文本更新触发器:
 *    - update_component_tsv: 在components更新时自动更新tsv字段
 */

-- [知识库——用户表] 从下到上的触发器(DONE)
-- 触发条件：
-- 1、知识库表中创建了新的知识库
-- 2、知识库中的所有权进行变更（即知识库行实例进行update时）
CREATE OR REPLACE FUNCTION update_user_knowledge_uuids()
RETURNS TRIGGER AS $$
BEGIN
    -- 处理新user_id（INSERT/UPDATE）
    IF TG_OP = 'INSERT' THEN
        BEGIN
            -- 对相应用户行加锁
            PERFORM 1 FROM chunk_schema.users
            WHERE id = NEW.user_id FOR UPDATE;

            UPDATE chunk_schema.users
            SET knowledge_ids = array_append(knowledge_ids,NEW.id)
            WHERE id = NEW.user_id;
        END;
    ELSIF TG_OP = 'UPDATE' THEN
        BEGIN
            -- 对相应用户行加锁
            PERFORM 1 FROM chunk_schema.users
            WHERE id = OLD.user_id FOR UPDATE;

            UPDATE chunk_schema.users
            SET knowledge_ids = array_remove(knowledge_ids, OLD.id)
            WHERE id = OLD.user_id;

            UPDATE chunk_schema.users
            SET knowledge_ids = array_append(array_remove(knowledge_ids, OLD.id), NEW.id)
            WHERE id = NEW.user_id;
        END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- [文档——知识库] 从下到上的触发器(DONE)
-- 触发条件：
-- 1、文档表中创建了新的文档
-- 2、文档表中的文档转移了所有权
CREATE OR REPLACE FUNCTION update_knowledge_base_document_ids()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        BEGIN
            PERFORM 1 FROM chunk_schema.knowledge_bases
            WHERE id = NEW.knowledge_base_id FOR UPDATE;

            UPDATE chunk_schema.knowledge_bases
            SET document_ids = array_append(document_ids, NEW.id)
            WHERE id = NEW.knowledge_base_id;
        END;

    ELSIF TG_OP = 'UPDATE' THEN
        -- 本身区分无意义，只是说明可以转移所有权,故使用这种写法以防忘记
        IF OLD.knowledge_base_id <> NEW.knowledge_base_id THEN
            BEGIN
                PERFORM 1 FROM chunk_schema.knowledge_bases
                WHERE id = NEW.knowledge_base_id FOR UPDATE;
                -- 从旧知识库移除
                UPDATE chunk_schema.knowledge_bases
                SET document_ids = array_remove(document_ids, OLD.id)
                WHERE id = OLD.knowledge_base_id;
                -- 添加到新知识库
                UPDATE chunk_schema.knowledge_bases
                SET document_ids = array_append(document_ids, NEW.id)
                WHERE id = NEW.knowledge_base_id;
            END;
        ELSIF OLD.knowledge_base_id = NEW.knowledge_base_id THEN
            -- 添加到新知识库
            UPDATE chunk_schema.knowledge_bases
            SET document_ids = array_append(array_remove(document_ids, OLD.id), NEW.id)
            WHERE id = NEW.knowledge_base_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 组件表触发器函数：插入或者更新时更新文档表中的组件ids
CREATE OR REPLACE FUNCTION update_component_document_ids()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE chunk_schema.documents
        SET component_ids = array_append(component_ids, NEW.id)
        WHERE id = NEW.document_id;

    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE chunk_schema.documents
        SET component_ids = array_append(array_remove(component_ids, OLD.id), NEW.id)
        WHERE id = NEW.document_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

--删除文档的触发器逻辑
CREATE OR REPLACE FUNCTION delete_document()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE chunk_schema.documents
        SET component_ids = array_remove(component_ids, OLD.id)
        WHERE id = OLD.id;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- 确保doc_position唯一性和顺序的触发器函数
CREATE OR REPLACE FUNCTION ensure_doc_position_uniqueness()
RETURNS TRIGGER AS $$
DECLARE
    max_position INTEGER;
BEGIN
    -- 如果有冲突或者没有指定doc_position
    IF NEW.doc_position IS NULL OR EXISTS (
        SELECT 1 FROM (
            SELECT doc_position 
            FROM chunk_schema.components 
            WHERE document_id = NEW.document_id AND id != NEW.id AND doc_position = NEW.doc_position
        ) AS conflicts
    ) THEN
        -- 获取当前最大的doc_position
        SELECT COALESCE(MAX(position), -1) INTO max_position
        FROM (
            SELECT doc_position AS position 
            FROM chunk_schema.components 
            WHERE document_id = NEW.document_id
        ) AS positions;
        
        -- 设置为最大值+1
        NEW.doc_position := max_position + 1;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 更新文档内容的触发器函数
CREATE OR REPLACE FUNCTION update_document_content()
RETURNS TRIGGER AS $$
DECLARE
    doc_id TEXT;
    combined_text TEXT := '';
    ordered_components TEXT[] := '{}';
BEGIN
    -- 确定要更新的文档ID
    IF TG_OP = 'DELETE' THEN
        doc_id := OLD.document_id;
    ELSE
        doc_id := NEW.document_id;
    END IF;

    -- 按doc_position排序获取所有组件
    SELECT 
        array_agg(id ORDER BY doc_position),
        string_agg(text, E'\n\n' ORDER BY doc_position)
    INTO ordered_components, combined_text
    FROM chunk_schema.components
    WHERE document_id = doc_id;

    -- 更新文档的component_ids和text
    UPDATE chunk_schema.documents
    SET 
        component_ids = ordered_components,
        text = combined_text
    WHERE id = doc_id;

    RETURN NULL; -- 这是一个AFTER触发器，返回值不重要
END;
$$ LANGUAGE plpgsql;

-- 更新组件tsv字段的触发器函数
CREATE OR REPLACE FUNCTION update_component_tsv()
RETURNS TRIGGER AS $$
DECLARE
    doc_name TEXT;
    combined_text TEXT;
BEGIN
    -- 获取文档名称
    SELECT name INTO doc_name
    FROM chunk_schema.documents
    WHERE id = NEW.document_id;

    -- 组合文档名称和组件文本
    combined_text := doc_name || ' ' || COALESCE(NEW.text, '');

    -- 使用pg_jieba进行分词并更新tsv字段
    NEW.tsv := to_tsvector('jieba', combined_text);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 从chunks表同步到components表的触发器函数
CREATE OR REPLACE FUNCTION sync_chunks_to_components()
RETURNS TRIGGER AS $$
BEGIN
    -- 检查components表中是否已存在此ID的记录
    IF EXISTS (SELECT 1 FROM chunk_schema.components WHERE id = NEW.id) THEN
        -- 更新已存在的记录
        UPDATE chunk_schema.components
        SET document_id = NEW.document_id,
            doc_position = NEW.doc_position,
            text = NEW.text,
            embedding = NEW.embedding,
            type = 'chunk'
        WHERE id = NEW.id;
    ELSE
        -- 插入新纪录
        INSERT INTO chunk_schema.components (id, document_id, doc_position, type, text, embedding)
        VALUES (NEW.id, NEW.document_id, NEW.doc_position, 'chunk', NEW.text, NEW.embedding);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 从photos表同步到components表的触发器函数
CREATE OR REPLACE FUNCTION sync_photos_to_components()
RETURNS TRIGGER AS $$
BEGIN
    -- 检查components表中是否已存在此ID的记录
    IF EXISTS (SELECT 1 FROM chunk_schema.components WHERE id = NEW.id) THEN
        -- 更新已存在的记录
        UPDATE chunk_schema.components
        SET document_id = NEW.document_id,
            doc_position = NEW.doc_position,
            text = NEW.text,
            embedding = NEW.embedding,
            type = NEW.type
        WHERE id = NEW.id;
    ELSE
        -- 插入新纪录
        INSERT INTO chunk_schema.components (id, document_id, doc_position, type, text, embedding)
        VALUES (NEW.id, NEW.document_id, NEW.doc_position, NEW.type, NEW.text, NEW.embedding);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为知识库表创建触发器
CREATE TRIGGER knowledge_base_after_insert_update
AFTER INSERT OR UPDATE ON chunk_schema.knowledge_bases
FOR EACH ROW EXECUTE FUNCTION update_user_knowledge_uuids();

-- 为文档表创建触发器
CREATE TRIGGER document_after_trigger
AFTER INSERT OR UPDATE ON chunk_schema.documents
FOR EACH ROW EXECUTE FUNCTION update_knowledge_base_document_ids();

-- 为components表创建触发器
CREATE TRIGGER components_after_trigger
AFTER INSERT OR UPDATE ON chunk_schema.components
FOR EACH ROW EXECUTE FUNCTION update_component_document_ids();

-- 为components表创建触发器，确保doc_position唯一
CREATE TRIGGER components_before_insert_update
BEFORE INSERT OR UPDATE ON chunk_schema.components
FOR EACH ROW EXECUTE FUNCTION ensure_doc_position_uniqueness();

-- 为components表创建触发器，自动更新tsv字段
CREATE TRIGGER components_tsv_trigger
BEFORE INSERT OR UPDATE ON chunk_schema.components
FOR EACH ROW EXECUTE FUNCTION update_component_tsv();

-- 为chunks表创建触发器，自动同步到components表
CREATE TRIGGER chunks_after_insert_update
AFTER INSERT OR UPDATE ON chunk_schema.chunks
FOR EACH ROW EXECUTE FUNCTION sync_chunks_to_components();

-- 为photos表创建触发器，自动同步到components表
CREATE TRIGGER photos_after_insert_update
AFTER INSERT OR UPDATE ON chunk_schema.photos
FOR EACH ROW EXECUTE FUNCTION sync_photos_to_components();

-- 为components表创建触发器，自动更新文档的完整文本内容
CREATE TRIGGER components_update_document_text
AFTER INSERT OR UPDATE OR DELETE ON chunk_schema.components
FOR EACH ROW EXECUTE FUNCTION update_document_content();