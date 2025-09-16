/*
 * 文件名: 022-create-access-key-management.sql
 * 作用: 创建访问密钥管理的额外功能和视图
 * 分类: 用户和权限管理扩展
 * 执行顺序: 在021-create-users.sql之后执行
 * 
 * 功能说明:
 * 1. 创建访问密钥管理视图
 * 2. 创建访问密钥使用统计视图
 * 3. 创建定期清理任务
 * 4. 创建权限检查辅助函数
 */

-- ================================
-- 访问密钥管理视图 (Access Key Management Views)
-- ================================

-- 访问密钥概览视图（隐藏敏感信息）
CREATE OR REPLACE VIEW chunk_schema.access_keys_overview AS
SELECT 
    id,
    user_id,
    name,
    description,
    scopes,
    is_active,
    total_requests,
    requests_today,
    requests_this_hour,
    max_requests_per_hour,
    max_requests_per_day,
    max_file_size_mb,
    max_knowledge_bases,
    can_create_kb,
    can_delete_files,
    can_share_files,
    can_export_data,
    created_at,
    expires_at,
    last_used_at,
    -- 计算字段
    CASE 
        WHEN expires_at IS NULL THEN 'never'
        WHEN expires_at > CURRENT_TIMESTAMP THEN 'active'
        ELSE 'expired'
    END as expiry_status,
    CASE 
        WHEN max_requests_per_hour IS NOT NULL THEN 
            ROUND((requests_this_hour::FLOAT / max_requests_per_hour::FLOAT) * 100, 2)
        ELSE NULL
    END as hourly_usage_percent,
    CASE 
        WHEN max_requests_per_day IS NOT NULL THEN 
            ROUND((requests_today::FLOAT / max_requests_per_day::FLOAT) * 100, 2)
        ELSE NULL
    END as daily_usage_percent
FROM chunk_schema.access_keys;

-- 用户访问密钥统计视图
CREATE OR REPLACE VIEW chunk_schema.user_access_key_stats AS
SELECT 
    u.id as user_id,
    u.username,
    u.display_name,
    COUNT(ak.id) as total_keys,
    COUNT(ak.id) FILTER (WHERE ak.is_active = TRUE) as active_keys,
    COUNT(ak.id) FILTER (WHERE ak.expires_at IS NOT NULL AND ak.expires_at < CURRENT_TIMESTAMP) as expired_keys,
    SUM(ak.total_requests) as total_requests_all_keys,
    SUM(ak.requests_today) as requests_today_all_keys,
    MAX(ak.last_used_at) as last_activity,
    MIN(ak.created_at) as first_key_created
FROM chunk_schema.users u
LEFT JOIN chunk_schema.access_keys ak ON u.id = ak.user_id
GROUP BY u.id, u.username, u.display_name;

-- 访问密钥使用趋势视图（按小时）
CREATE OR REPLACE VIEW chunk_schema.access_key_usage_trends AS
SELECT 
    ak.id,
    ak.name,
    ak.user_id,
    DATE_TRUNC('hour', ual.created_at) as hour_bucket,
    COUNT(*) as requests_in_hour,
    COUNT(DISTINCT ual.action_type) as unique_actions,
    AVG(CASE WHEN ual.action_result = 'success' THEN 1 ELSE 0 END) as success_rate
FROM chunk_schema.access_keys ak
LEFT JOIN chunk_schema.user_activity_logs ual ON ak.user_id = ual.user_id
WHERE ual.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
GROUP BY ak.id, ak.name, ak.user_id, DATE_TRUNC('hour', ual.created_at)
ORDER BY hour_bucket DESC;

-- ================================
-- 访问密钥管理函数 (Access Key Management Functions)
-- ================================

-- 创建新的访问密钥（带完整配置）
CREATE OR REPLACE FUNCTION create_access_key(
    p_user_id TEXT,
    p_name TEXT,
    p_description TEXT DEFAULT NULL,
    p_scopes TEXT[] DEFAULT '{"read", "write"}'::TEXT[],
    p_expires_at TIMESTAMPTZ DEFAULT NULL,
    p_max_requests_per_hour INTEGER DEFAULT 1000,
    p_max_requests_per_day INTEGER DEFAULT 10000,
    p_max_file_size_mb INTEGER DEFAULT 100,
    p_max_knowledge_bases INTEGER DEFAULT 10,
    p_can_create_kb BOOLEAN DEFAULT TRUE,
    p_can_delete_files BOOLEAN DEFAULT TRUE,
    p_can_share_files BOOLEAN DEFAULT TRUE,
    p_can_export_data BOOLEAN DEFAULT TRUE,
    p_allowed_ips TEXT[] DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    new_key_id TEXT;
    new_access_key TEXT;
BEGIN
    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM chunk_schema.users WHERE id = p_user_id) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'user_not_found',
            'message', 'User does not exist'
        );
    END IF;
    
    -- 生成新的访问密钥
    new_access_key := generate_access_key();
    new_key_id := 'ak_' || encode(gen_random_bytes(16), 'hex');
    
    -- 插入新的访问密钥
    INSERT INTO chunk_schema.access_keys (
        id, user_id, access_key, name, description, scopes, expires_at,
        max_requests_per_hour, max_requests_per_day, max_file_size_mb, max_knowledge_bases,
        can_create_kb, can_delete_files, can_share_files, can_export_data, allowed_ips
    ) VALUES (
        new_key_id, p_user_id, new_access_key, p_name, p_description, p_scopes, p_expires_at,
        p_max_requests_per_hour, p_max_requests_per_day, p_max_file_size_mb, p_max_knowledge_bases,
        p_can_create_kb, p_can_delete_files, p_can_share_files, p_can_export_data, p_allowed_ips
    );
    
    RETURN jsonb_build_object(
        'success', true,
        'key_id', new_key_id,
        'access_key', new_access_key,
        'message', 'Access key created successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 更新访问密钥配置
CREATE OR REPLACE FUNCTION update_access_key_config(
    p_key_id TEXT,
    p_config JSONB
) RETURNS JSONB AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    -- 更新访问密钥配置
    UPDATE chunk_schema.access_keys 
    SET 
        name = COALESCE((p_config->>'name')::TEXT, name),
        description = COALESCE((p_config->>'description')::TEXT, description),
        is_active = COALESCE((p_config->>'is_active')::BOOLEAN, is_active),
        expires_at = CASE 
            WHEN p_config ? 'expires_at' THEN (p_config->>'expires_at')::TIMESTAMPTZ
            ELSE expires_at
        END,
        max_requests_per_hour = CASE 
            WHEN p_config ? 'max_requests_per_hour' THEN (p_config->>'max_requests_per_hour')::INTEGER
            ELSE max_requests_per_hour
        END,
        max_requests_per_day = CASE 
            WHEN p_config ? 'max_requests_per_day' THEN (p_config->>'max_requests_per_day')::INTEGER
            ELSE max_requests_per_day
        END,
        max_file_size_mb = CASE 
            WHEN p_config ? 'max_file_size_mb' THEN (p_config->>'max_file_size_mb')::INTEGER
            ELSE max_file_size_mb
        END,
        max_knowledge_bases = CASE 
            WHEN p_config ? 'max_knowledge_bases' THEN (p_config->>'max_knowledge_bases')::INTEGER
            ELSE max_knowledge_bases
        END,
        can_create_kb = COALESCE((p_config->>'can_create_kb')::BOOLEAN, can_create_kb),
        can_delete_files = COALESCE((p_config->>'can_delete_files')::BOOLEAN, can_delete_files),
        can_share_files = COALESCE((p_config->>'can_share_files')::BOOLEAN, can_share_files),
        can_export_data = COALESCE((p_config->>'can_export_data')::BOOLEAN, can_export_data),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_key_id;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    IF updated_count = 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'key_not_found',
            'message', 'Access key not found'
        );
    END IF;
    
    RETURN jsonb_build_object(
        'success', true,
        'message', 'Access key updated successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 撤销访问密钥
CREATE OR REPLACE FUNCTION revoke_access_key(p_key_id TEXT) RETURNS JSONB AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    UPDATE chunk_schema.access_keys 
    SET is_active = FALSE,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_key_id;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    
    IF updated_count = 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'key_not_found',
            'message', 'Access key not found'
        );
    END IF;
    
    RETURN jsonb_build_object(
        'success', true,
        'message', 'Access key revoked successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================
-- 定期清理任务 (Cleanup Tasks)
-- ================================

-- 重置每日请求计数器（应该在每天午夜运行）
CREATE OR REPLACE FUNCTION reset_daily_request_counters() RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    UPDATE chunk_schema.access_keys 
    SET requests_today = 0,
        requests_this_hour = 0,
        last_request_reset_date = CURRENT_DATE,
        last_request_reset_hour = EXTRACT(HOUR FROM CURRENT_TIMESTAMP)
    WHERE last_request_reset_date < CURRENT_DATE;
    
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 清理长期未使用的访问密钥（可选）
CREATE OR REPLACE FUNCTION cleanup_unused_access_keys(days_unused INTEGER DEFAULT 90) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM chunk_schema.access_keys 
    WHERE last_used_at < CURRENT_TIMESTAMP - (days_unused || ' days')::INTERVAL
      AND is_active = FALSE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================
-- 权限检查辅助函数 (Permission Helper Functions)
-- ================================

-- 简化的权限检查函数（向后兼容）
CREATE OR REPLACE FUNCTION validate_access_key_simple(token TEXT) RETURNS TEXT AS $$
DECLARE
    validation_result JSONB;
BEGIN
    validation_result := validate_access_key(token);
    
    IF (validation_result->>'valid')::BOOLEAN THEN
        RETURN validation_result->>'user_id';
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
