/*
 * 文件名: 025-add-webhooks.sql
 * 作用: 创建 Webhook 和通知相关表
 * 分类: SaaS Webhook 和通知系统
 * 执行顺序: 在 024-add-usage-metrics-and-billing.sql 之后执行
 *
 * 功能说明:
 * 1. 创建 Webhook 端点配置表 (webhook_endpoints)
 * 2. 创建 Webhook 事件日志表 (webhook_events)
 * 3. 创建 Webhook 管理函数
 */

-- ================================
-- Webhook 端点配置表 (Webhook Endpoints)
-- ================================

-- Webhook 端点配置表
CREATE TABLE IF NOT EXISTS unifiles.webhook_endpoints (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('wh_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,

    -- Webhook 配置
    url TEXT NOT NULL,                               -- Webhook URL
    secret_key TEXT NOT NULL,                        -- 用于签名验证的密钥
    events TEXT[] NOT NULL,                          -- ['file.uploaded', 'quota.exceeded', 'payment.failed']

    -- 描述
    description TEXT,                                -- Webhook 描述

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,                  -- 是否启用
    status TEXT DEFAULT 'active',                    -- 'active', 'disabled', 'failed'
    failure_count INTEGER DEFAULT 0,                 -- 失败次数
    last_failure_at TIMESTAMPTZ,                     -- 最后失败时间
    last_success_at TIMESTAMPTZ,                     -- 最后成功时间

    -- 配置
    retry_policy JSONB DEFAULT '{"max_retries": 3, "retry_delay_seconds": 60}',
    timeout_seconds INTEGER DEFAULT 30,              -- 超时时间（秒）

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_webhook_endpoints_status
        CHECK (status IN ('active', 'disabled', 'failed')),
    CONSTRAINT chk_webhook_endpoints_positive_timeout
        CHECK (timeout_seconds > 0 AND timeout_seconds <= 300),
    CONSTRAINT chk_webhook_endpoints_url_format
        CHECK (url ~ '^https?://'),
    CONSTRAINT chk_webhook_endpoints_events_not_empty
        CHECK (array_length(events, 1) > 0)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_user ON unifiles.webhook_endpoints(user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_status ON unifiles.webhook_endpoints(status) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_webhook_endpoints_events ON unifiles.webhook_endpoints USING gin(events);

-- ================================
-- Webhook 事件日志表 (Webhook Events)
-- ================================

-- Webhook 事件日志表
CREATE TABLE IF NOT EXISTS unifiles.webhook_events (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('evt_' || encode(gen_random_bytes(16), 'hex')),
    webhook_id TEXT NOT NULL REFERENCES unifiles.webhook_endpoints(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,

    -- 事件信息
    event_type TEXT NOT NULL,                        -- 'file.uploaded', 'quota.exceeded', etc.
    payload JSONB NOT NULL,                          -- 事件数据

    -- 发送状态
    status TEXT DEFAULT 'pending',                   -- 'pending', 'sent', 'failed', 'cancelled'
    attempts INTEGER DEFAULT 0,                      -- 尝试次数
    last_attempt_at TIMESTAMPTZ,                     -- 最后尝试时间
    next_retry_at TIMESTAMPTZ,                       -- 下次重试时间

    -- 响应信息
    response_code INTEGER,                           -- HTTP 响应码
    response_body TEXT,                              -- HTTP 响应内容（截断）
    error_message TEXT,                              -- 错误信息

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,                        -- 完成时间（成功或最终失败）

    -- 约束
    CONSTRAINT chk_webhook_events_status
        CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    CONSTRAINT chk_webhook_events_attempts_positive
        CHECK (attempts >= 0)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_webhook_events_webhook ON unifiles.webhook_events(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_user ON unifiles.webhook_events(user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON unifiles.webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_webhook_events_created ON unifiles.webhook_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_next_retry ON unifiles.webhook_events(next_retry_at) WHERE status = 'pending';

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为 webhook_endpoints 添加更新时间戳触发器
CREATE TRIGGER trigger_webhook_endpoints_updated_at
    BEFORE UPDATE ON unifiles.webhook_endpoints
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- ================================
-- Webhook 管理函数
-- ================================

-- 创建 Webhook 端点
CREATE OR REPLACE FUNCTION create_webhook_endpoint(
    p_user_id TEXT,
    p_url TEXT,
    p_events TEXT[],
    p_description TEXT DEFAULT NULL,
    p_timeout_seconds INTEGER DEFAULT 30
) RETURNS JSONB AS $$
DECLARE
    new_webhook_id TEXT;
    new_secret_key TEXT;
BEGIN
    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM unifiles.users WHERE id = p_user_id) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'user_not_found',
            'message', 'User does not exist'
        );
    END IF;

    -- 生成 secret_key
    new_secret_key := 'whsec_' || encode(gen_random_bytes(32), 'hex');
    new_webhook_id := 'wh_' || encode(gen_random_bytes(16), 'hex');

    -- 插入新的 Webhook 端点
    INSERT INTO unifiles.webhook_endpoints (
        id, user_id, url, secret_key, events, description, timeout_seconds
    ) VALUES (
        new_webhook_id, p_user_id, p_url, new_secret_key, p_events, p_description, p_timeout_seconds
    );

    RETURN jsonb_build_object(
        'success', true,
        'webhook_id', new_webhook_id,
        'secret_key', new_secret_key,
        'message', 'Webhook endpoint created successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建 Webhook 事件
CREATE OR REPLACE FUNCTION create_webhook_event(
    p_user_id TEXT,
    p_event_type TEXT,
    p_payload JSONB
) RETURNS VOID AS $$
DECLARE
    webhook RECORD;
BEGIN
    -- 查找订阅了此事件类型的所有活跃 Webhook
    FOR webhook IN
        SELECT id, retry_policy
        FROM unifiles.webhook_endpoints
        WHERE user_id = p_user_id
          AND is_active = TRUE
          AND status = 'active'
          AND p_event_type = ANY(events)
    LOOP
        -- 为每个匹配的 Webhook 创建事件
        INSERT INTO unifiles.webhook_events (
            webhook_id,
            user_id,
            event_type,
            payload,
            status,
            next_retry_at
        ) VALUES (
            webhook.id,
            p_user_id,
            p_event_type,
            p_payload,
            'pending',
            CURRENT_TIMESTAMP  -- 立即尝试发送
        );
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 更新 Webhook 事件状态
CREATE OR REPLACE FUNCTION update_webhook_event_status(
    p_event_id TEXT,
    p_status TEXT,
    p_response_code INTEGER DEFAULT NULL,
    p_response_body TEXT DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    event RECORD;
    webhook RECORD;
    retry_delay INTEGER;
    max_retries INTEGER;
BEGIN
    -- 获取事件信息
    SELECT * INTO event
    FROM unifiles.webhook_events
    WHERE id = p_event_id;

    IF event IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'event_not_found'
        );
    END IF;

    -- 获取 Webhook 配置
    SELECT * INTO webhook
    FROM unifiles.webhook_endpoints
    WHERE id = event.webhook_id;

    -- 提取重试策略
    max_retries := COALESCE((webhook.retry_policy->>'max_retries')::INTEGER, 3);
    retry_delay := COALESCE((webhook.retry_policy->>'retry_delay_seconds')::INTEGER, 60);

    -- 更新事件状态
    IF p_status = 'sent' THEN
        -- 成功发送
        UPDATE unifiles.webhook_events
        SET status = 'sent',
            attempts = attempts + 1,
            last_attempt_at = CURRENT_TIMESTAMP,
            completed_at = CURRENT_TIMESTAMP,
            response_code = p_response_code,
            response_body = LEFT(p_response_body, 1000)  -- 截断响应体
        WHERE id = p_event_id;

        -- 更新 Webhook 状态
        UPDATE unifiles.webhook_endpoints
        SET last_success_at = CURRENT_TIMESTAMP,
            failure_count = 0,
            status = 'active'
        WHERE id = event.webhook_id;

    ELSIF p_status = 'failed' THEN
        -- 发送失败
        IF event.attempts + 1 >= max_retries THEN
            -- 达到最大重试次数，标记为最终失败
            UPDATE unifiles.webhook_events
            SET status = 'failed',
                attempts = attempts + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                completed_at = CURRENT_TIMESTAMP,
                response_code = p_response_code,
                error_message = p_error_message
            WHERE id = p_event_id;

            -- 更新 Webhook 失败计数
            UPDATE unifiles.webhook_endpoints
            SET failure_count = failure_count + 1,
                last_failure_at = CURRENT_TIMESTAMP,
                status = CASE
                    WHEN failure_count + 1 >= 10 THEN 'failed'
                    ELSE status
                END
            WHERE id = event.webhook_id;
        ELSE
            -- 安排重试
            UPDATE unifiles.webhook_events
            SET status = 'pending',
                attempts = attempts + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                next_retry_at = CURRENT_TIMESTAMP + (retry_delay || ' seconds')::INTERVAL,
                response_code = p_response_code,
                error_message = p_error_message
            WHERE id = p_event_id;
        END IF;
    END IF;

    RETURN jsonb_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取待发送的 Webhook 事件
CREATE OR REPLACE FUNCTION get_pending_webhook_events(
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    event_id TEXT,
    webhook_id TEXT,
    webhook_url TEXT,
    secret_key TEXT,
    event_type TEXT,
    payload JSONB,
    timeout_seconds INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        we.id as event_id,
        we.webhook_id,
        wh.url as webhook_url,
        wh.secret_key,
        we.event_type,
        we.payload,
        wh.timeout_seconds
    FROM unifiles.webhook_events we
    JOIN unifiles.webhook_endpoints wh ON we.webhook_id = wh.id
    WHERE we.status = 'pending'
      AND we.next_retry_at <= CURRENT_TIMESTAMP
      AND wh.is_active = TRUE
      AND wh.status = 'active'
    ORDER BY we.next_retry_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================
-- 常用事件类型定义（注释说明）
-- ================================

/*
支持的事件类型列表：

文件相关：
- file.uploaded: 文件上传完成
- file.processed: 文件处理完成
- file.deleted: 文件删除
- file.shared: 文件分享

知识库相关：
- kb.created: 知识库创建
- kb.updated: 知识库更新
- kb.deleted: 知识库删除

配额相关：
- quota.warning: 配额警告（达到 80%）
- quota.exceeded: 配额超限

支付相关：
- payment.succeeded: 支付成功
- payment.failed: 支付失败
- subscription.created: 订阅创建
- subscription.updated: 订阅更新
- subscription.cancelled: 订阅取消
- subscription.expired: 订阅过期

安全相关：
- security.api_key_created: API 密钥创建
- security.api_key_revoked: API 密钥撤销
- security.suspicious_activity: 可疑活动检测
*/
