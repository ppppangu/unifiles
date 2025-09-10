/*
 * 文件名: 051-create-rls-policies.sql
 * 作用: 为所有表创建行级安全策略(RLS)
 * 说明: 
 * 1. 使用事务级设置，避免连接复用的安全问题
 * 2. 每个事务开始时需要显式设置用户ID
 * 3. 相比应用层过滤，仍有性能优势
 */

-- 创建获取当前用户ID的安全函数
CREATE OR REPLACE FUNCTION get_current_user_id() RETURNS TEXT AS $$
BEGIN
    -- 使用事务级别的设置，避免连接复用问题
    RETURN current_setting('request.jwt.claims', true)::json->>'user_id';
EXCEPTION
    -- 如果没有JWT claims，返回NULL（将拒绝所有访问）
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 备用方案：使用应用层传入的用户ID（需要在每个事务中设置）
CREATE OR REPLACE FUNCTION get_app_user_id() RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.user_id', true);
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 启用RLS并创建策略 - chunk_schema.users表
ALTER TABLE chunk_schema.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_policy ON chunk_schema.users
    USING (id = get_app_user_id());

-- 启用RLS并创建策略 - chunk_schema.knowledge_bases表
ALTER TABLE chunk_schema.knowledge_bases ENABLE ROW LEVEL SECURITY;

CREATE POLICY knowledge_bases_policy ON chunk_schema.knowledge_bases
    USING (user_id = get_app_user_id());

-- 启用RLS并创建策略 - chunk_schema.documents表
ALTER TABLE chunk_schema.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_policy ON chunk_schema.documents
    USING (knowledge_base_id IN (
        SELECT id FROM chunk_schema.knowledge_bases 
        WHERE user_id = get_app_user_id()
    ));

-- 启用RLS并创建策略 - chunk_schema.components表
ALTER TABLE chunk_schema.components ENABLE ROW LEVEL SECURITY;

CREATE POLICY components_policy ON chunk_schema.components
    USING (document_id IN (
        SELECT d.id FROM chunk_schema.documents d
        JOIN chunk_schema.knowledge_bases kb ON d.knowledge_base_id = kb.id
        WHERE kb.user_id = get_app_user_id()
    ));

-- 启用RLS并创建策略 - chunk_schema.chunks表
ALTER TABLE chunk_schema.chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY chunks_policy ON chunk_schema.chunks
    USING (document_id IN (
        SELECT d.id FROM chunk_schema.documents d
        JOIN chunk_schema.knowledge_bases kb ON d.knowledge_base_id = kb.id
        WHERE kb.user_id = get_app_user_id()
    ));

-- 启用RLS并创建策略 - chunk_schema.photos表
ALTER TABLE chunk_schema.photos ENABLE ROW LEVEL SECURITY;

CREATE POLICY photos_policy ON chunk_schema.photos
    USING (document_id IN (
        SELECT d.id FROM chunk_schema.documents d
        JOIN chunk_schema.knowledge_bases kb ON d.knowledge_base_id = kb.id
        WHERE kb.user_id = get_app_user_id()
    ));

-- 启用RLS并创建策略 - chunk_schema.logical_hierarchy表
ALTER TABLE chunk_schema.logical_hierarchy ENABLE ROW LEVEL SECURITY;

CREATE POLICY logical_hierarchy_policy ON chunk_schema.logical_hierarchy
    USING (user_id = get_app_user_id());

-- 启用RLS并创建策略 - chunk_schema.files表
ALTER TABLE chunk_schema.files ENABLE ROW LEVEL SECURITY;

CREATE POLICY files_policy ON chunk_schema.files
    USING (user_id = get_app_user_id());

-- 启用RLS并创建策略 - chunk_schema.file_processing_logs表
ALTER TABLE chunk_schema.file_processing_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY file_processing_logs_policy ON chunk_schema.file_processing_logs
    USING (user_id = get_app_user_id());

-- 启用RLS并创建策略 - procedure.session表
ALTER TABLE procedure.session ENABLE ROW LEVEL SECURITY;

CREATE POLICY session_policy ON procedure.session
    USING (user_id = get_app_user_id());

-- 启用RLS并创建策略 - procedure.conversation表
ALTER TABLE procedure.conversation ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversation_policy ON procedure.conversation
    USING (user_id = get_app_user_id());

/*
 * 安全使用说明:
 * 
 * 方案1: 在每个事务开始时设置用户ID（推荐）
 * ```python
 * async with conn.transaction():
 *     await conn.execute("SET LOCAL app.user_id = $1", user_id)
 *     # 执行业务查询...
 * ```
 * 
 * 方案2: 暂时禁用RLS，在应用层控制（如果性能要求极高）
 * ```python
 * # 只对超级用户有效
 * await conn.execute("SET row_security = off")
 * ```
 * 
 * 优势：
 * - LOCAL设置只在当前事务有效，事务结束自动清除
 * - 避免连接复用的安全问题
 * - 数据库层过滤仍有性能优势
 */