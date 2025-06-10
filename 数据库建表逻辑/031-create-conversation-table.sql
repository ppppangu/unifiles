/*
 * 文件名: 031-create-conversation-table.sql
 * 作用: 创建对话管理相关的表结构
 * 组成:
 * 1. procedure命名空间 - 用于管理对话过程
 * 2. session表 - 存储会话信息，包括用户ID、对话历史等
 * 3. conversation表 - 存储具体对话内容，包括角色、内容、推理过程等
 * 4. 索引 - 为高效查询创建必要的索引
 */

-- 对话过程
CREATE SCHEMA IF NOT EXISTS procedure;

-- 会话注册
CREATE TABLE IF NOT EXISTS procedure.session (
	id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    all_conversation TEXT[]
);

-- 对话过程
CREATE TABLE IF NOT EXISTS procedure.conversation (
	id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES chunk_schema.users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL REFERENCES procedure.session(id) ON DELETE CASCADE,
    sequence_number INTEGER,
    role VARCHAR(50) NOT NULL,
    reasoning_content TEXT,
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_session
    ON procedure.conversation(user_id, session_id);
