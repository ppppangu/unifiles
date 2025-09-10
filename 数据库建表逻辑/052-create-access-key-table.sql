/*
 * 文件名: 052-create-access-key-table.sql
 * 作用: 创建用户访问密钥表，用于Bearer token认证
 * 说明: 
 * 1. 支持用户多个access_key管理
 * 2. 支持token过期时间设置
 * 3. 记录token使用情况
 * 4. 支持token的启用/禁用
 */

-- 创建访问密钥表
CREATE TABLE IF NOT EXISTS chunk_schema.access_keys (
    id TEXT PRIMARY KEY DEFAULT ('ak_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    access_key TEXT NOT NULL UNIQUE,        -- 实际的Bearer token
    name TEXT NOT NULL,                     -- token的描述名称
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,                 -- 过期时间，NULL表示永不过期
    last_used_at TIMESTAMPTZ,               -- 最后使用时间
    is_active BOOLEAN DEFAULT TRUE,         -- 是否启用
    scopes TEXT[] DEFAULT '{"read", "write"}'::TEXT[], -- 权限范围
    
    -- 确保access_key的唯一性和安全性
    CONSTRAINT access_key_length_check CHECK (length(access_key) >= 32),
    CONSTRAINT access_key_format_check CHECK (access_key ~ '^[a-zA-Z0-9_-]+$')
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_access_keys_user_id ON chunk_schema.access_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_access_keys_token ON chunk_schema.access_keys(access_key) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_access_keys_active ON chunk_schema.access_keys(is_active, expires_at);

-- 创建函数：生成安全的access_key
CREATE OR REPLACE FUNCTION generate_access_key() RETURNS TEXT AS $$
BEGIN
    -- 生成64字符的安全随机字符串
    RETURN 'sk_' || encode(gen_random_bytes(32), 'hex');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建函数：验证并获取用户ID通过access_key
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

-- 创建函数：清理过期的access_key
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

-- 创建触发器：自动生成access_key
CREATE OR REPLACE FUNCTION auto_generate_access_key() RETURNS TRIGGER AS $$
BEGIN
    -- 如果没有提供access_key，自动生成一个
    IF NEW.access_key IS NULL OR NEW.access_key = '' THEN
        NEW.access_key = generate_access_key();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER access_keys_auto_generate
    BEFORE INSERT ON chunk_schema.access_keys
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_access_key();

-- 启用RLS并创建策略
ALTER TABLE chunk_schema.access_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY access_keys_policy ON chunk_schema.access_keys
    USING (user_id = get_app_user_id());

-- 创建用于管理access_key的便捷视图（隐藏敏感信息）
CREATE OR REPLACE VIEW chunk_schema.user_access_keys AS
SELECT 
    id,
    user_id,
    name,
    created_at,
    expires_at,
    last_used_at,
    is_active,
    scopes,
    -- 只显示token的前8位和后4位，中间用*替代
    CASE 
        WHEN LENGTH(access_key) > 12 THEN 
            LEFT(access_key, 8) || REPEAT('*', LENGTH(access_key) - 12) || RIGHT(access_key, 4)
        ELSE 
            REPEAT('*', LENGTH(access_key))
    END AS masked_access_key
FROM chunk_schema.access_keys;

-- 为视图启用RLS
ALTER VIEW chunk_schema.user_access_keys SET ROW SECURITY = ON;

/*
 * 使用示例:
 * 
 * -- 为用户创建新的access_key
 * INSERT INTO chunk_schema.access_keys (user_id, name) 
 * VALUES ('user123', 'API Access Token');
 * 
 * -- 验证token并获取用户ID
 * SELECT validate_access_key('sk_abcd1234...') AS user_id;
 * 
 * -- 查看用户的所有access_key（脱敏）
 * SELECT * FROM chunk_schema.user_access_keys WHERE user_id = 'user123';
 * 
 * -- 禁用某个access_key
 * UPDATE chunk_schema.access_keys SET is_active = FALSE WHERE id = 'ak_xxx';
 * 
 * -- 清理过期token
 * SELECT cleanup_expired_access_keys();
 */