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
    
    -- 权限和配置
    scopes TEXT[] DEFAULT '{"read", "write"}'::TEXT[],     -- 权限范围
    
    -- 状态信息
    is_active BOOLEAN DEFAULT TRUE,                       -- 是否启用
    
    -- 时间信息
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    expires_at TIMESTAMPTZ,                               -- 过期时间，NULL表示永不过期
    last_used_at TIMESTAMPTZ,                             -- 最后使用时间
    
    -- 外键约束
    CONSTRAINT fk_access_keys_user_id 
        FOREIGN KEY (user_id) REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    
    -- 确保access_key的唯一性和安全性
    CONSTRAINT chk_access_keys_length CHECK (length(access_key) >= 32),
    CONSTRAINT chk_access_keys_format CHECK (access_key ~ '^[a-zA-Z0-9_-]+$')
);

-- ================================
-- 索引 (Indexes)
-- ================================

-- 提高access_keys查询性能的索引
CREATE INDEX IF NOT EXISTS idx_access_keys_user_id ON chunk_schema.access_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_access_keys_token ON chunk_schema.access_keys(access_key) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_access_keys_active ON chunk_schema.access_keys(is_active, expires_at);

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

-- 验证并获取用户ID通过access_key
CREATE OR REPLACE FUNCTION validate_access_key(token TEXT) RETURNS TEXT AS $$
DECLARE
    user_id_result TEXT;
BEGIN
    -- 查找有效的access_key并返回对应的user_id
    SELECT ak.user_id INTO user_id_result
    FROM chunk_schema.access_keys ak
    WHERE ak.access_key = token
      AND ak.is_active = TRUE
      AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP);
    
    -- 如果找到有效token，更新最后使用时间
    IF user_id_result IS NOT NULL THEN
        UPDATE chunk_schema.access_keys 
        SET last_used_at = CURRENT_TIMESTAMP
        WHERE access_key = token;
    END IF;
    
    RETURN user_id_result;
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