/*
 * 文件名: 021-create-users.sql
 * 作用: 创建用户和权限管理表
 * 分类: 用户和权限管理
 * 执行顺序: 第二步 - 在扩展创建后，其他业务表之前执行
 * 
 * 功能说明:
 * 1. users表: 存储用户基本信息和知识库关联
 * 2. 支持用户级别的权限控制
 * 3. 为后续的多租户架构做准备
 * 
 * 设计原则:
 * - 用户ID使用TEXT类型，支持外部系统集成
 * - knowledge_ids数组存储用户关联的知识库
 * - 包含创建和更新时间戳
 * - 支持软删除（通过状态字段）
 */

-- ================================
-- 用户管理表 (User Management)
-- ================================

-- 用户表
CREATE TABLE IF NOT EXISTS chunk_schema.users (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 用户唯一标识
    
    -- 用户基本信息
    username TEXT,                                          -- 用户名（可选）
    email TEXT,                                            -- 邮箱（可选）
    password TEXT,                                         -- 密码
    display_name TEXT,                                     -- 显示名称
    
    -- 权限和状态
    user_status TEXT DEFAULT 'active',                     -- 用户状态
    user_role TEXT DEFAULT 'user',                         -- 用户角色
    
    -- 知识库关联
    knowledge_ids TEXT[] DEFAULT '{}',                      -- 关联的知识库ID列表
    
    -- 配置信息
    user_settings JSONB DEFAULT '{}',                      -- 用户配置（如偏好设置）
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 更新时间
    last_login_at TIMESTAMPTZ,                             -- 最后登录时间
    
    -- 约束
    CONSTRAINT chk_users_status 
        CHECK (user_status IN ('active', 'inactive', 'suspended', 'deleted')),
    CONSTRAINT chk_users_role 
        CHECK (user_role IN ('admin', 'user', 'readonly'))
);


-- ================================
-- 用户操作日志表 (User Activity Log)
-- ================================

-- 用户操作日志表
CREATE TABLE IF NOT EXISTS chunk_schema.user_activity_logs (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 日志ID
    user_id TEXT NOT NULL,                                 -- 用户ID
    
    -- 操作信息
    action_type TEXT NOT NULL,                             -- 操作类型
    resource_type TEXT,                                    -- 资源类型
    resource_id TEXT,                                      -- 资源ID
    
    -- 操作详情
    action_description TEXT,                               -- 操作描述
    action_metadata JSONB DEFAULT '{}',                   -- 操作元数据
    
    -- 结果信息
    action_result TEXT DEFAULT 'success',                 -- 操作结果
    error_message TEXT,                                    -- 错误信息（如果有）
    
    -- 环境信息
    ip_address TEXT,                                       -- IP地址
    user_agent TEXT,                                       -- 用户代理
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 操作时间
    
    -- 外键约束
    CONSTRAINT fk_user_activity_logs_user_id 
        FOREIGN KEY (user_id) REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_user_activity_logs_action_result 
        CHECK (action_result IN ('success', 'failed', 'partial'))
);

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 创建更新时间戳的触发器函数
CREATE OR REPLACE FUNCTION chunk_schema.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为用户表添加更新时间戳触发器
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON chunk_schema.users
    FOR EACH ROW
    EXECUTE FUNCTION chunk_schema.update_updated_at_column();

-- ================================
-- 用户访问密钥表 (User Access Keys)
-- ================================

-- 访问密钥表
CREATE TABLE IF NOT EXISTS chunk_schema.access_keys (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('ak_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL,                                 -- 用户ID

    -- 密钥信息
    access_key TEXT NOT NULL UNIQUE,                      -- 实际的Bearer token
    name TEXT NOT NULL,                                    -- token的描述名称
    description TEXT,                                      -- 详细描述

    -- 权限和配置
    scopes TEXT[] DEFAULT '{"read", "write"}'::TEXT[],     -- 权限范围
    allowed_ips TEXT[],                                    -- 允许的IP地址列表，NULL表示不限制
    allowed_domains TEXT[],                                -- 允许的域名列表，NULL表示不限制

    -- 使用限制
    max_requests_per_hour INTEGER DEFAULT 1000,           -- 每小时最大请求数，NULL表示不限制
    max_requests_per_day INTEGER DEFAULT 10000,           -- 每天最大请求数，NULL表示不限制
    max_file_size_mb INTEGER DEFAULT 100,                 -- 最大文件大小(MB)，NULL表示不限制
    max_knowledge_bases INTEGER DEFAULT 10,               -- 最大知识库数量，NULL表示不限制

    -- 功能限制
    can_create_kb BOOLEAN DEFAULT TRUE,                   -- 是否可以创建知识库
    can_delete_files BOOLEAN DEFAULT TRUE,                -- 是否可以删除文件
    can_share_files BOOLEAN DEFAULT TRUE,                 -- 是否可以分享文件
    can_export_data BOOLEAN DEFAULT TRUE,                 -- 是否可以导出数据

    -- 状态信息
    is_active BOOLEAN DEFAULT TRUE,                       -- 是否启用

    -- 使用统计
    total_requests INTEGER DEFAULT 0,                     -- 总请求数
    requests_today INTEGER DEFAULT 0,                     -- 今日请求数
    requests_this_hour INTEGER DEFAULT 0,                 -- 本小时请求数
    last_request_reset_date DATE DEFAULT CURRENT_DATE,    -- 上次重置请求计数的日期
    last_request_reset_hour INTEGER DEFAULT EXTRACT(HOUR FROM CURRENT_TIMESTAMP), -- 上次重置小时计数的小时

    -- 时间信息
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    expires_at TIMESTAMPTZ,                               -- 过期时间，NULL表示永不过期
    last_used_at TIMESTAMPTZ,                             -- 最后使用时间

    -- 外键约束
    CONSTRAINT fk_access_keys_user_id
        FOREIGN KEY (user_id) REFERENCES chunk_schema.users(id) ON DELETE CASCADE,

    -- 确保access_key的唯一性和安全性
    CONSTRAINT chk_access_keys_length CHECK (length(access_key) >= 32),
    CONSTRAINT chk_access_keys_format CHECK (access_key ~ '^[a-zA-Z0-9_-]+$'),

    -- 限制值的合理性检查
    CONSTRAINT chk_access_keys_max_requests_hour_positive
        CHECK (max_requests_per_hour IS NULL OR max_requests_per_hour > 0),
    CONSTRAINT chk_access_keys_max_requests_day_positive
        CHECK (max_requests_per_day IS NULL OR max_requests_per_day > 0),
    CONSTRAINT chk_access_keys_max_file_size_positive
        CHECK (max_file_size_mb IS NULL OR max_file_size_mb > 0),
    CONSTRAINT chk_access_keys_max_kb_positive
        CHECK (max_knowledge_bases IS NULL OR max_knowledge_bases > 0),
    CONSTRAINT chk_access_keys_requests_positive
        CHECK (total_requests >= 0 AND requests_today >= 0 AND requests_this_hour >= 0)
);

-- ================================
-- 索引 (Indexes)
-- ================================

-- 提高access_keys查询性能的索引
CREATE INDEX IF NOT EXISTS idx_access_keys_user_id ON chunk_schema.access_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_access_keys_token ON chunk_schema.access_keys(access_key) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_access_keys_active ON chunk_schema.access_keys(is_active, expires_at);
CREATE INDEX IF NOT EXISTS idx_access_keys_last_used ON chunk_schema.access_keys(last_used_at);
CREATE INDEX IF NOT EXISTS idx_access_keys_reset_date ON chunk_schema.access_keys(last_request_reset_date);
CREATE INDEX IF NOT EXISTS idx_access_keys_scopes ON chunk_schema.access_keys USING gin(scopes);

-- ================================
-- 密钥管理函数 (Key Management Functions)
-- ================================

-- 生成安全的access_key
CREATE OR REPLACE FUNCTION generate_access_key() RETURNS TEXT AS $$
BEGIN
    -- 生成64字符的安全随机字符串
    RETURN 'sk_' || encode(gen_random_bytes(32), 'hex');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 验证并获取用户ID通过access_key（增强版本，包含限制检查）
CREATE OR REPLACE FUNCTION validate_access_key(token TEXT, client_ip TEXT DEFAULT NULL) RETURNS JSONB AS $$
DECLARE
    result JSONB;
    ak_record RECORD;
    current_hour INTEGER;
    current_date DATE;
    requests_exceeded BOOLEAN := FALSE;
BEGIN
    current_hour := EXTRACT(HOUR FROM CURRENT_TIMESTAMP);
    current_date := CURRENT_DATE;

    -- 查找有效的access_key
    SELECT * INTO ak_record
    FROM chunk_schema.access_keys ak
    WHERE ak.access_key = token
      AND ak.is_active = TRUE
      AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP);

    -- 如果没找到有效token
    IF ak_record IS NULL THEN
        RETURN jsonb_build_object(
            'valid', false,
            'user_id', null,
            'error', 'invalid_token',
            'message', 'Token is invalid, expired, or inactive'
        );
    END IF;

    -- 检查IP限制
    IF ak_record.allowed_ips IS NOT NULL AND client_ip IS NOT NULL THEN
        IF NOT (client_ip = ANY(ak_record.allowed_ips)) THEN
            RETURN jsonb_build_object(
                'valid', false,
                'user_id', ak_record.user_id,
                'error', 'ip_not_allowed',
                'message', 'Client IP is not in the allowed list'
            );
        END IF;
    END IF;

    -- 重置请求计数器（如果需要）
    IF ak_record.last_request_reset_date < current_date THEN
        UPDATE chunk_schema.access_keys
        SET requests_today = 0,
            requests_this_hour = 0,
            last_request_reset_date = current_date,
            last_request_reset_hour = current_hour
        WHERE access_key = token;
        ak_record.requests_today := 0;
        ak_record.requests_this_hour := 0;
    ELSIF ak_record.last_request_reset_hour < current_hour THEN
        UPDATE chunk_schema.access_keys
        SET requests_this_hour = 0,
            last_request_reset_hour = current_hour
        WHERE access_key = token;
        ak_record.requests_this_hour := 0;
    END IF;

    -- 检查请求频率限制
    IF ak_record.max_requests_per_hour IS NOT NULL AND
       ak_record.requests_this_hour >= ak_record.max_requests_per_hour THEN
        requests_exceeded := TRUE;
    END IF;

    IF ak_record.max_requests_per_day IS NOT NULL AND
       ak_record.requests_today >= ak_record.max_requests_per_day THEN
        requests_exceeded := TRUE;
    END IF;

    IF requests_exceeded THEN
        RETURN jsonb_build_object(
            'valid', false,
            'user_id', ak_record.user_id,
            'error', 'rate_limit_exceeded',
            'message', 'Request rate limit exceeded'
        );
    END IF;

    -- 更新使用统计
    UPDATE chunk_schema.access_keys
    SET last_used_at = CURRENT_TIMESTAMP,
        total_requests = total_requests + 1,
        requests_today = requests_today + 1,
        requests_this_hour = requests_this_hour + 1
    WHERE access_key = token;

    -- 返回成功结果
    RETURN jsonb_build_object(
        'valid', true,
        'user_id', ak_record.user_id,
        'scopes', ak_record.scopes,
        'max_file_size_mb', ak_record.max_file_size_mb,
        'max_knowledge_bases', ak_record.max_knowledge_bases,
        'can_create_kb', ak_record.can_create_kb,
        'can_delete_files', ak_record.can_delete_files,
        'can_share_files', ak_record.can_share_files,
        'can_export_data', ak_record.can_export_data
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 清理过期的access_key
CREATE OR REPLACE FUNCTION cleanup_expired_access_keys() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM chunk_schema.access_keys
    WHERE expires_at IS NOT NULL
      AND expires_at < CURRENT_TIMESTAMP;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 检查用户权限的函数
CREATE OR REPLACE FUNCTION check_user_permission(
    token TEXT,
    permission_type TEXT,
    resource_info JSONB DEFAULT '{}'::JSONB
) RETURNS BOOLEAN AS $$
DECLARE
    validation_result JSONB;
    user_permissions JSONB;
BEGIN
    -- 验证token
    validation_result := validate_access_key(token);

    -- 如果token无效，返回false
    IF NOT (validation_result->>'valid')::BOOLEAN THEN
        RETURN FALSE;
    END IF;

    -- 检查具体权限
    CASE permission_type
        WHEN 'create_kb' THEN
            RETURN (validation_result->>'can_create_kb')::BOOLEAN;
        WHEN 'delete_files' THEN
            RETURN (validation_result->>'can_delete_files')::BOOLEAN;
        WHEN 'share_files' THEN
            RETURN (validation_result->>'can_share_files')::BOOLEAN;
        WHEN 'export_data' THEN
            RETURN (validation_result->>'can_export_data')::BOOLEAN;
        WHEN 'upload_file' THEN
            -- 检查文件大小限制
            IF resource_info ? 'file_size_mb' THEN
                DECLARE
                    max_size INTEGER;
                    file_size INTEGER;
                BEGIN
                    max_size := (validation_result->>'max_file_size_mb')::INTEGER;
                    file_size := (resource_info->>'file_size_mb')::INTEGER;

                    IF max_size IS NOT NULL AND file_size > max_size THEN
                        RETURN FALSE;
                    END IF;
                END;
            END IF;
            RETURN 'write' = ANY(ARRAY(SELECT jsonb_array_elements_text(validation_result->'scopes')));
        ELSE
            -- 默认检查read权限
            RETURN 'read' = ANY(ARRAY(SELECT jsonb_array_elements_text(validation_result->'scopes')));
    END CASE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取用户使用统计的函数
CREATE OR REPLACE FUNCTION get_access_key_stats(token TEXT) RETURNS JSONB AS $$
DECLARE
    ak_record RECORD;
BEGIN
    SELECT * INTO ak_record
    FROM chunk_schema.access_keys
    WHERE access_key = token AND is_active = TRUE;

    IF ak_record IS NULL THEN
        RETURN jsonb_build_object('error', 'Token not found');
    END IF;

    RETURN jsonb_build_object(
        'total_requests', ak_record.total_requests,
        'requests_today', ak_record.requests_today,
        'requests_this_hour', ak_record.requests_this_hour,
        'max_requests_per_hour', ak_record.max_requests_per_hour,
        'max_requests_per_day', ak_record.max_requests_per_day,
        'last_used_at', ak_record.last_used_at,
        'created_at', ak_record.created_at,
        'expires_at', ak_record.expires_at
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 自动生成access_key触发器函数
CREATE OR REPLACE FUNCTION auto_generate_access_key() RETURNS TRIGGER AS $$
BEGIN
    -- 如果没有提供access_key，自动生成一个
    IF NEW.access_key IS NULL OR NEW.access_key = '' THEN
        NEW.access_key = generate_access_key();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 触发器：自动生成access_key
CREATE TRIGGER access_keys_auto_generate
    BEFORE INSERT ON chunk_schema.access_keys
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_access_key();

-- ================================
-- 基础数据 (Initial Data)
-- ================================

-- 插入系统管理员用户（示例）
-- 注意: 生产环境中应该通过安全的方式创建管理员账户
INSERT INTO chunk_schema.users (id, username, display_name, user_role, user_status)
VALUES ('system-admin', 'admin', 'System Administrator', 'admin', 'active')
ON CONFLICT (id) DO NOTHING;