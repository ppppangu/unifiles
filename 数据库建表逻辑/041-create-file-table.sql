/*
 * 文件名: 041-create-file-table.sql
 * 作用: 创建文件管理相关表结构
 * 组成:
 * 1. files - 文件信息表，存储上传的文件基本信息
 * 2. file_processing_logs - 文件处理日志表，跟踪文件处理状态和进度
 * 3. 索引 - 为高效查询创建必要的索引
 * 
 * 说明:
 * - 文件表参考OpenAI Files API设计，支持有状态的文件管理
 * - 通过user_id与用户关联，实现用户级别的文件隔离
 * - 支持文件处理全生命周期的状态跟踪
 */

-- 创建文件信息表
CREATE TABLE IF NOT EXISTS chunk_schema.files (
    id TEXT PRIMARY KEY,                                    -- 文件唯一标识符，格式：file-xxx
    user_id TEXT NOT NULL,                                  -- 用户ID (外键)
    object TEXT DEFAULT 'file',                             -- 对象类型 (固定为'file')
    bytes INTEGER NOT NULL,                                 -- 文件大小 (字节)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,       -- 创建时间
    filename TEXT NOT NULL,                                 -- 原始文件名
    purpose TEXT DEFAULT 'assistants',                      -- 文件用途 (assistants, fine-tune等)
    status TEXT DEFAULT 'uploaded',                         -- 文件状态
    status_details TEXT,                                    -- 状态详细信息
    mime_type TEXT,                                         -- MIME类型
    file_path TEXT,                                         -- 服务器端文件路径
    raw_file_public_url TEXT,                               -- 原始文件公开URL
    processed_file_url TEXT,                                -- 处理后文件URL
    metadata JSONB DEFAULT '{}',                            -- 扩展元数据
    
    -- 外键约束
    CONSTRAINT fk_files_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES chunk_schema.users(id) 
        ON DELETE CASCADE,
        
    -- 状态约束
    CONSTRAINT chk_files_status 
        CHECK (status IN ('uploaded', 'processing', 'processed', 'error', 'deleted')),
        
    -- 用途约束
    CONSTRAINT chk_files_purpose 
        CHECK (purpose IN ('assistants', 'fine-tune', 'batch', 'vision'))
);

-- 创建文件处理日志表
CREATE TABLE IF NOT EXISTS chunk_schema.file_processing_logs (
    id TEXT PRIMARY KEY,                                    -- 日志唯一标识符
    file_id TEXT NOT NULL,                                  -- 关联文件ID
    user_id TEXT NOT NULL,                                  -- 用户ID
    status TEXT NOT NULL,                                   -- 处理状态
    stage TEXT NOT NULL,                                    -- 处理阶段
    message TEXT,                                           -- 处理消息
    details JSONB DEFAULT '{}',                             -- 详细信息
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,       -- 开始时间
    completed_at TIMESTAMPTZ,                               -- 完成时间
    error_info JSONB,                                       -- 错误信息
    
    -- 外键约束
    CONSTRAINT fk_logs_file_id 
        FOREIGN KEY (file_id) 
        REFERENCES chunk_schema.files(id) 
        ON DELETE CASCADE,
        
    CONSTRAINT fk_logs_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES chunk_schema.users(id) 
        ON DELETE CASCADE,
        
    -- 状态约束
    CONSTRAINT chk_logs_status 
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
        
    -- 阶段约束
    CONSTRAINT chk_logs_stage 
        CHECK (stage IN ('upload', 'validation', 'parsing', 'processing', 'indexing', 'completion'))
);