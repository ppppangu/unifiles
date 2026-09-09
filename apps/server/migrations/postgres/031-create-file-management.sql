/*
 * 文件名: 031-create-file-management.sql
 * 作用: 创建文件管理层表结构
 * 分类: 文件管理层
 * 执行顺序: 第三步 - 在用户表创建后执行
 * 
 * 功能说明:
 * 1. files表: 存储上传文件的基本信息和元数据
 * 2. file_processing_logs表: 记录文件处理的详细日志和进度
 * 3. 支持文件去重、状态跟踪、错误处理
 * 4. 为后续的内容提取和知识库构建提供基础
 * 
 * 设计原则:
 * - 文件哈希用于去重和完整性校验
 * - 详细的处理阶段和状态跟踪
 * - 灵活的元数据存储（JSONB）
 * - 完善的约束和外键关系
 */

-- ================================
-- 存储配置表 (Storage Configuration) - 简化版
-- ================================

-- 存储配置表 - 简洁设计
CREATE TABLE IF NOT EXISTS unifiles.storage_configs (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 配置唯一标识
    
    -- 基本信息
    storage_name TEXT NOT NULL,                            -- 存储名称（用于显示）
    connection_config JSONB NOT NULL,                     -- 连接配置（包含provider和所有连接参数）
    
    -- 元数据
    is_active BOOLEAN DEFAULT TRUE,                       -- 是否启用
    config_source TEXT DEFAULT 'manual',                  -- 配置来源：'env' 或 'manual'
    public_url_prefix TEXT,                               -- 公网URL前缀
    metadata JSONB DEFAULT '{}',                          -- 额外元数据
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 更新时间
    
    -- 检查约束
    CONSTRAINT chk_storage_configs_config_source 
        CHECK (config_source IN ('env', 'manual')),
    CONSTRAINT chk_storage_configs_connection_has_provider
        CHECK (connection_config ? 'provider')
);

-- ================================
-- 文件基础管理表 (File Management)
-- ================================

-- 文件表
CREATE TABLE IF NOT EXISTS unifiles.files (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 文件唯一标识
    
    -- 用户关联
    user_id TEXT NOT NULL,                                 -- 文件所有者
    
    -- 文件基本信息
    filename TEXT NOT NULL,                                -- 原始文件名
    mime_type TEXT,                                        -- MIME类型
    file_extension TEXT,                                   -- 文件扩展名
    purpose TEXT[] DEFAULT '{}',                           -- 上传目的：'fine-tuning' 或 'extract'
    
    -- 文件大小和存储
    bytes BIGINT NOT NULL,                                 -- 文件大小（字节，使用BIGINT支持大文件）
    file_size_readable TEXT,                               -- 可读的文件大小（如：1.2MB）
    
    -- 文件校验和存储信息
    file_hash TEXT,                                        -- 文件哈希（用于去重）
    hash_algorithm TEXT DEFAULT 'sha256',                  -- 哈希算法
    
    -- 存储信息（简化存储配置）
    storage_config_id TEXT,                                -- 存储配置ID（关联storage_configs表）
    storage_path TEXT NOT NULL,                           -- 存储路径（相对于配置的base_path）
    
    -- 访问地址（自动生成，不存储在数据库）
    is_public BOOLEAN DEFAULT FALSE,                      -- 是否公网可访问    
    
    -- 文件状态管理
    status TEXT DEFAULT 'active',                          -- 文件状态：active/error/deleted
    upload_source TEXT DEFAULT 'web',                     -- 上传来源
    is_deleted BOOLEAN DEFAULT FALSE,                      -- 软删除标记
    
    -- 文件分类和标签
    file_category TEXT,                                    -- 文件分类
    tags TEXT[] DEFAULT '{}',                              -- 文件标签
    
    -- 元数据信息
    metadata JSONB DEFAULT '{}',                           -- 文件元数据
    processing_config JSONB DEFAULT '{}',                 -- 处理配置
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 更新时间
    uploaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,     -- 上传时间
    processed_at TIMESTAMPTZ,                              -- 处理完成时间
    
    -- 外键约束
    CONSTRAINT fk_files_user_id 
        FOREIGN KEY (user_id) REFERENCES unifiles.users(id) ON DELETE CASCADE,
    CONSTRAINT fk_files_storage_config_id 
        FOREIGN KEY (storage_config_id) REFERENCES unifiles.storage_configs(id) ON DELETE SET NULL,
    
    -- 检查约束
    CONSTRAINT chk_files_status 
        CHECK (status IN ('active', 'error', 'deleted')),
    CONSTRAINT chk_files_purpose
        CHECK (
            purpose <@ ARRAY['fine-tuning', 'extract']::TEXT[] AND
            array_length(purpose, 1) > 0
        ),
    CONSTRAINT chk_files_upload_source 
        CHECK (upload_source IN ('web', 'api', 'batch', 'sync')),
    CONSTRAINT chk_files_bytes_positive 
        CHECK (bytes >= 0),
    CONSTRAINT chk_files_hash_algorithm 
        CHECK (hash_algorithm IN ('md5', 'sha1', 'sha256', 'sha512'))
);

-- ================================
-- 文件处理日志表 (Processing Logs)
-- ================================

-- 文件处理日志表（简化版）
CREATE TABLE IF NOT EXISTS unifiles.file_processing_logs (
    -- 主键标识
    id TEXT PRIMARY KEY,                                    -- 日志唯一标识
    
    -- 文件关联
    file_id TEXT NOT NULL,                                 -- 关联的文件ID
    
    -- 处理信息
    stage TEXT NOT NULL,                                   -- 处理阶段
    status TEXT NOT NULL,                                  -- 处理状态
    message TEXT,                                          -- 处理消息
    error_details JSONB,                                   -- 错误详情
    
    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,      -- 创建时间
    
    -- 外键约束
    CONSTRAINT fk_file_processing_logs_file_id 
        FOREIGN KEY (file_id) REFERENCES unifiles.files(id) ON DELETE CASCADE,
    
    -- 检查约束
    CONSTRAINT chk_file_processing_logs_status 
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT chk_file_processing_logs_stage 
        CHECK (stage IN ('upload', 'ocr_extraction'))
);



-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为storage_configs表添加更新时间戳触发器
CREATE TRIGGER trigger_storage_configs_updated_at
    BEFORE UPDATE ON unifiles.storage_configs
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为files表添加更新时间戳触发器
CREATE TRIGGER trigger_files_updated_at
    BEFORE UPDATE ON unifiles.files
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- ================================
-- 初始数据 (Initial Data)
-- ================================

-- 插入默认存储配置
INSERT INTO unifiles.storage_configs (id, storage_name, connection_config, is_active, public_url_prefix, config_source)
VALUES 
    ('default-local', 'Local Storage', '{"provider": "local", "base_path": "/uploads", "create_if_missing": true}', true, 'http://localhost:8000/files', 'env'),
    ('example-minio', 'MinIO Object Storage', '{"provider": "minio", "endpoint": "localhost:9000", "access_key": "<minio-access-key>", "secret_key": "<minio-secret-key>", "bucket_name": "unifiles", "region": "us-east-1", "secure": false}', false, 'https://minio.example.com/bucket', 'env')
ON CONFLICT (id) DO NOTHING;

