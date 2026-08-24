/*
 * 文件名: 024-add-usage-metrics-and-billing.sql
 * 作用: 创建使用量追踪和账单管理表
 * 分类: SaaS 使用量追踪和计费
 * 执行顺序: 在 023-add-subscriptions.sql 之后执行
 *
 * 功能说明:
 * 1. 创建使用量指标表 (usage_metrics)
 * 2. 创建账单记录表 (billing_invoices)
 * 3. 创建配额管理函数
 * 4. 创建使用量记录函数
 */

-- ================================
-- 使用量指标表 (Usage Metrics)
-- ================================

-- 使用量指标表（按天/小时聚合）
CREATE TABLE IF NOT EXISTS unifiles.usage_metrics (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('um_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,
    access_key_id TEXT REFERENCES unifiles.access_keys(id) ON DELETE SET NULL,

    -- 时间维度
    metric_date DATE NOT NULL,
    metric_hour INTEGER,                             -- NULL表示全天聚合，0-23表示小时级别

    -- 使用量指标
    api_calls INTEGER DEFAULT 0,                     -- API调用次数
    files_uploaded INTEGER DEFAULT 0,                -- 上传文件数
    files_downloaded INTEGER DEFAULT 0,              -- 下载文件数
    storage_bytes_used BIGINT DEFAULT 0,             -- 存储使用量（字节）
    bandwidth_bytes_out BIGINT DEFAULT 0,            -- 带宽使用量（字节）
    ocr_pages_processed INTEGER DEFAULT 0,           -- OCR处理页数
    ai_extractions INTEGER DEFAULT 0,                -- AI提取次数

    -- 成本追踪
    estimated_cost_usd DECIMAL(10,4) DEFAULT 0,      -- 估算成本（美元）

    -- 请求详情
    requests_by_endpoint JSONB DEFAULT '{}',         -- {"/files": 100, "/kb": 50}
    error_count INTEGER DEFAULT 0,                   -- 错误次数

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 唯一约束：每个用户每天（或每小时）只有一条记录
    CONSTRAINT uq_usage_metrics_user_date_hour
        UNIQUE (user_id, metric_date, metric_hour),

    -- 检查约束
    CONSTRAINT chk_usage_metrics_hour_range
        CHECK (metric_hour IS NULL OR (metric_hour >= 0 AND metric_hour <= 23)),
    CONSTRAINT chk_usage_metrics_positive_values
        CHECK (
            api_calls >= 0 AND
            files_uploaded >= 0 AND
            files_downloaded >= 0 AND
            storage_bytes_used >= 0 AND
            bandwidth_bytes_out >= 0 AND
            ocr_pages_processed >= 0 AND
            ai_extractions >= 0 AND
            error_count >= 0
        )
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_usage_metrics_user_date ON unifiles.usage_metrics(user_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_usage_metrics_date ON unifiles.usage_metrics(metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_usage_metrics_access_key ON unifiles.usage_metrics(access_key_id) WHERE access_key_id IS NOT NULL;

-- ================================
-- 账单记录表 (Billing Invoices)
-- ================================

-- 账单记录表
CREATE TABLE IF NOT EXISTS unifiles.billing_invoices (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('inv_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,
    subscription_id TEXT REFERENCES unifiles.user_subscriptions(id) ON DELETE SET NULL,

    -- 账单信息
    invoice_number TEXT UNIQUE NOT NULL,             -- 账单编号，如 "INV-2025-001"
    invoice_date DATE DEFAULT CURRENT_DATE,          -- 账单日期
    due_date DATE,                                   -- 到期日期

    -- 金额
    subtotal_usd DECIMAL(10,2) NOT NULL,             -- 小计（美元）
    tax_usd DECIMAL(10,2) DEFAULT 0,                 -- 税费（美元）
    total_usd DECIMAL(10,2) NOT NULL,                -- 总计（美元）
    currency TEXT DEFAULT 'USD',                     -- 货币类型

    -- 状态
    status TEXT DEFAULT 'draft',                     -- 'draft', 'open', 'paid', 'void', 'uncollectible'
    paid_at TIMESTAMPTZ,                             -- 支付时间

    -- 支付集成
    stripe_invoice_id TEXT UNIQUE,                   -- Stripe账单ID
    stripe_charge_id TEXT,                           -- Stripe收费ID
    payment_method TEXT,                             -- 'card', 'bank_transfer', 'paypal'

    -- 账单明细
    line_items JSONB DEFAULT '[]',                   -- [{"description": "Pro Plan", "amount": 29.00}]
    usage_breakdown JSONB DEFAULT '{}',              -- {"api_calls": 5000, "storage_gb": 10}

    -- 备注
    notes TEXT,                                      -- 备注信息

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_billing_invoices_status
        CHECK (status IN ('draft', 'open', 'paid', 'void', 'uncollectible')),
    CONSTRAINT chk_billing_invoices_positive_amounts
        CHECK (subtotal_usd >= 0 AND tax_usd >= 0 AND total_usd >= 0)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_billing_invoices_user ON unifiles.billing_invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_subscription ON unifiles.billing_invoices(subscription_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_status ON unifiles.billing_invoices(status);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_invoice_date ON unifiles.billing_invoices(invoice_date DESC);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_stripe_invoice ON unifiles.billing_invoices(stripe_invoice_id);

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为 usage_metrics 添加更新时间戳触发器
CREATE TRIGGER trigger_usage_metrics_updated_at
    BEFORE UPDATE ON unifiles.usage_metrics
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为 billing_invoices 添加更新时间戳触发器
CREATE TRIGGER trigger_billing_invoices_updated_at
    BEFORE UPDATE ON unifiles.billing_invoices
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- ================================
-- 配额管理函数
-- ================================

-- 检查用户配额
CREATE OR REPLACE FUNCTION check_user_quota(
    p_user_id TEXT,
    quota_type TEXT,                                 -- 'api_calls', 'storage', 'files_upload'
    requested_amount BIGINT DEFAULT 1
) RETURNS JSONB AS $$
DECLARE
    subscription RECORD;
    plan RECORD;
    current_usage BIGINT;
    quota_limit BIGINT;
BEGIN
    -- 获取用户当前订阅和套餐
    SELECT us.*, sp.* INTO subscription
    FROM unifiles.user_subscriptions us
    JOIN unifiles.subscription_plans sp ON us.plan_id = sp.id
    WHERE us.user_id = p_user_id
      AND us.status = 'active'
      AND (us.current_period_end IS NULL OR us.current_period_end > CURRENT_TIMESTAMP)
    ORDER BY us.current_period_start DESC
    LIMIT 1;

    -- 如果没有活跃订阅，使用免费套餐
    IF subscription IS NULL THEN
        SELECT * INTO plan
        FROM unifiles.subscription_plans
        WHERE plan_name = 'free'
        LIMIT 1;

        -- 将免费套餐的数据复制到subscription记录中
        subscription.max_files_per_month := plan.max_files_per_month;
        subscription.max_storage_gb := plan.max_storage_gb;
        subscription.max_api_calls_per_month := plan.max_api_calls_per_month;
    END IF;

    -- 根据quota_type获取当前使用量和限制
    CASE quota_type
        WHEN 'api_calls' THEN
            -- 获取本月API调用数
            SELECT COALESCE(SUM(api_calls), 0) INTO current_usage
            FROM unifiles.usage_metrics
            WHERE user_id = p_user_id
              AND metric_date >= DATE_TRUNC('month', CURRENT_DATE)
              AND metric_hour IS NULL;  -- 只统计日级别聚合

            quota_limit := subscription.max_api_calls_per_month;

        WHEN 'storage' THEN
            -- 获取当前存储使用量（GB）
            SELECT COALESCE(SUM(bytes), 0) / (1024.0 * 1024.0 * 1024.0) INTO current_usage
            FROM unifiles.files
            WHERE user_id = p_user_id AND is_deleted = FALSE;

            quota_limit := subscription.max_storage_gb;

        WHEN 'files_upload' THEN
            -- 获取本月上传文件数
            SELECT COALESCE(SUM(files_uploaded), 0) INTO current_usage
            FROM unifiles.usage_metrics
            WHERE user_id = p_user_id
              AND metric_date >= DATE_TRUNC('month', CURRENT_DATE)
              AND metric_hour IS NULL;

            quota_limit := subscription.max_files_per_month;

        ELSE
            RETURN jsonb_build_object('error', 'Unknown quota type');
    END CASE;

    -- 检查是否超出配额
    IF quota_limit IS NULL THEN
        -- 无限配额
        RETURN jsonb_build_object(
            'allowed', true,
            'quota_type', quota_type,
            'current_usage', current_usage,
            'limit', 'unlimited'
        );
    ELSIF (current_usage + requested_amount) > quota_limit THEN
        RETURN jsonb_build_object(
            'allowed', false,
            'quota_type', quota_type,
            'current_usage', current_usage,
            'limit', quota_limit,
            'requested', requested_amount,
            'would_exceed_by', (current_usage + requested_amount) - quota_limit
        );
    ELSE
        RETURN jsonb_build_object(
            'allowed', true,
            'quota_type', quota_type,
            'current_usage', current_usage,
            'limit', quota_limit,
            'remaining', quota_limit - current_usage - requested_amount
        );
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 记录使用量
CREATE OR REPLACE FUNCTION record_usage(
    p_user_id TEXT,
    p_access_key_id TEXT,
    p_endpoint TEXT,
    p_metrics JSONB                                  -- {"api_calls": 1, "files_uploaded": 1, "bandwidth_bytes": 1024}
) RETURNS VOID AS $$
DECLARE
    today DATE := CURRENT_DATE;
    current_hour INTEGER := EXTRACT(HOUR FROM CURRENT_TIMESTAMP);
BEGIN
    -- 插入或更新小时级别的指标
    INSERT INTO unifiles.usage_metrics (
        user_id,
        access_key_id,
        metric_date,
        metric_hour,
        api_calls,
        files_uploaded,
        files_downloaded,
        bandwidth_bytes_out,
        ocr_pages_processed,
        ai_extractions,
        requests_by_endpoint
    ) VALUES (
        p_user_id,
        p_access_key_id,
        today,
        current_hour,
        COALESCE((p_metrics->>'api_calls')::INTEGER, 0),
        COALESCE((p_metrics->>'files_uploaded')::INTEGER, 0),
        COALESCE((p_metrics->>'files_downloaded')::INTEGER, 0),
        COALESCE((p_metrics->>'bandwidth_bytes')::BIGINT, 0),
        COALESCE((p_metrics->>'ocr_pages')::INTEGER, 0),
        COALESCE((p_metrics->>'ai_extractions')::INTEGER, 0),
        jsonb_build_object(p_endpoint, 1)
    )
    ON CONFLICT (user_id, metric_date, metric_hour)
    DO UPDATE SET
        api_calls = unifiles.usage_metrics.api_calls + COALESCE((p_metrics->>'api_calls')::INTEGER, 0),
        files_uploaded = unifiles.usage_metrics.files_uploaded + COALESCE((p_metrics->>'files_uploaded')::INTEGER, 0),
        files_downloaded = unifiles.usage_metrics.files_downloaded + COALESCE((p_metrics->>'files_downloaded')::INTEGER, 0),
        bandwidth_bytes_out = unifiles.usage_metrics.bandwidth_bytes_out + COALESCE((p_metrics->>'bandwidth_bytes')::BIGINT, 0),
        ocr_pages_processed = unifiles.usage_metrics.ocr_pages_processed + COALESCE((p_metrics->>'ocr_pages')::INTEGER, 0),
        ai_extractions = unifiles.usage_metrics.ai_extractions + COALESCE((p_metrics->>'ai_extractions')::INTEGER, 0),
        requests_by_endpoint = unifiles.usage_metrics.requests_by_endpoint || jsonb_build_object(
            p_endpoint,
            COALESCE((unifiles.usage_metrics.requests_by_endpoint->>p_endpoint)::INTEGER, 0) + 1
        ),
        updated_at = CURRENT_TIMESTAMP;

    -- 同时更新每日聚合（metric_hour = NULL）
    INSERT INTO unifiles.usage_metrics (
        user_id,
        access_key_id,
        metric_date,
        metric_hour,
        api_calls,
        files_uploaded,
        files_downloaded,
        bandwidth_bytes_out,
        ocr_pages_processed,
        ai_extractions,
        requests_by_endpoint
    ) VALUES (
        p_user_id,
        p_access_key_id,
        today,
        NULL,  -- 日级别聚合
        COALESCE((p_metrics->>'api_calls')::INTEGER, 0),
        COALESCE((p_metrics->>'files_uploaded')::INTEGER, 0),
        COALESCE((p_metrics->>'files_downloaded')::INTEGER, 0),
        COALESCE((p_metrics->>'bandwidth_bytes')::BIGINT, 0),
        COALESCE((p_metrics->>'ocr_pages')::INTEGER, 0),
        COALESCE((p_metrics->>'ai_extractions')::INTEGER, 0),
        jsonb_build_object(p_endpoint, 1)
    )
    ON CONFLICT (user_id, metric_date, metric_hour)
    DO UPDATE SET
        api_calls = unifiles.usage_metrics.api_calls + COALESCE((p_metrics->>'api_calls')::INTEGER, 0),
        files_uploaded = unifiles.usage_metrics.files_uploaded + COALESCE((p_metrics->>'files_uploaded')::INTEGER, 0),
        files_downloaded = unifiles.usage_metrics.files_downloaded + COALESCE((p_metrics->>'files_downloaded')::INTEGER, 0),
        bandwidth_bytes_out = unifiles.usage_metrics.bandwidth_bytes_out + COALESCE((p_metrics->>'bandwidth_bytes')::BIGINT, 0),
        ocr_pages_processed = unifiles.usage_metrics.ocr_pages_processed + COALESCE((p_metrics->>'ocr_pages')::INTEGER, 0),
        ai_extractions = unifiles.usage_metrics.ai_extractions + COALESCE((p_metrics->>'ai_extractions')::INTEGER, 0),
        requests_by_endpoint = unifiles.usage_metrics.requests_by_endpoint || jsonb_build_object(
            p_endpoint,
            COALESCE((unifiles.usage_metrics.requests_by_endpoint->>p_endpoint)::INTEGER, 0) + 1
        ),
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 获取用户使用统计
CREATE OR REPLACE FUNCTION get_user_usage_stats(
    p_user_id TEXT,
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    total_stats RECORD;
    daily_stats JSONB;
BEGIN
    -- 设置默认日期范围（如果未提供）
    IF p_start_date IS NULL THEN
        p_start_date := CURRENT_DATE - INTERVAL '30 days';
    END IF;

    IF p_end_date IS NULL THEN
        p_end_date := CURRENT_DATE;
    END IF;

    -- 获取总计统计
    SELECT
        COALESCE(SUM(api_calls), 0) as total_api_calls,
        COALESCE(SUM(files_uploaded), 0) as total_files_uploaded,
        COALESCE(SUM(files_downloaded), 0) as total_files_downloaded,
        COALESCE(SUM(bandwidth_bytes_out), 0) as total_bandwidth_bytes,
        COALESCE(SUM(ocr_pages_processed), 0) as total_ocr_pages,
        COALESCE(SUM(ai_extractions), 0) as total_ai_extractions
    INTO total_stats
    FROM unifiles.usage_metrics
    WHERE user_id = p_user_id
      AND metric_date BETWEEN p_start_date AND p_end_date
      AND metric_hour IS NULL;

    -- 获取每日统计
    SELECT jsonb_agg(
        jsonb_build_object(
            'date', metric_date,
            'api_calls', api_calls,
            'files_uploaded', files_uploaded,
            'files_downloaded', files_downloaded,
            'bandwidth_bytes', bandwidth_bytes_out
        ) ORDER BY metric_date
    ) INTO daily_stats
    FROM unifiles.usage_metrics
    WHERE user_id = p_user_id
      AND metric_date BETWEEN p_start_date AND p_end_date
      AND metric_hour IS NULL;

    RETURN jsonb_build_object(
        'user_id', p_user_id,
        'period', jsonb_build_object(
            'start_date', p_start_date,
            'end_date', p_end_date
        ),
        'totals', row_to_json(total_stats),
        'daily_breakdown', COALESCE(daily_stats, '[]'::JSONB)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
