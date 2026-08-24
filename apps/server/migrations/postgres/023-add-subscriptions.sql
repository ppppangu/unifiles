/*
 * 文件名: 023-add-subscriptions.sql
 * 作用: 创建订阅管理相关表
 * 分类: SaaS 订阅管理
 * 执行顺序: 在 022-create-access-key-management.sql 之后执行
 *
 * 功能说明:
 * 1. 创建订阅套餐表 (subscription_plans)
 * 2. 创建用户订阅表 (user_subscriptions)
 * 3. 创建订阅历史表 (subscription_history)
 * 4. 创建订阅管理相关函数
 */

-- ================================
-- 订阅套餐表 (Subscription Plans)
-- ================================

-- 订阅套餐表
CREATE TABLE IF NOT EXISTS unifiles.subscription_plans (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('plan_' || encode(gen_random_bytes(16), 'hex')),

    -- 套餐基本信息
    plan_name TEXT NOT NULL UNIQUE,                   -- 'free', 'pro', 'enterprise'
    plan_type TEXT NOT NULL,                          -- 'free', 'paid'
    display_name TEXT NOT NULL,                       -- 显示名称，如 "Professional Plan"
    description TEXT,                                 -- 套餐描述

    -- 配额限制
    max_files_per_month INTEGER,                     -- 每月最大文件数，NULL表示无限制
    max_storage_gb INTEGER,                          -- 最大存储空间(GB)，NULL表示无限制
    max_api_calls_per_month INTEGER,                 -- 每月最大API调用数，NULL表示无限制
    max_file_size_mb INTEGER DEFAULT 100,            -- 最大文件大小(MB)
    max_knowledge_bases INTEGER DEFAULT 10,          -- 最大知识库数量
    max_api_keys INTEGER DEFAULT 5,                  -- 最大API密钥数量

    -- 速率限制
    rate_limit_per_hour INTEGER DEFAULT 1000,        -- 每小时速率限制
    rate_limit_per_day INTEGER DEFAULT 10000,        -- 每天速率限制

    -- 功能权限
    features JSONB DEFAULT '{}',                     -- {"ocr": true, "ai_extraction": true, "priority_support": true}

    -- 定价信息
    price_monthly_usd DECIMAL(10,2),                 -- 月付价格（美元）
    price_yearly_usd DECIMAL(10,2),                  -- 年付价格（美元）
    currency TEXT DEFAULT 'USD',                     -- 货币类型

    -- 状态信息
    is_active BOOLEAN DEFAULT TRUE,                  -- 是否可用
    is_public BOOLEAN DEFAULT TRUE,                  -- 是否公开显示
    sort_order INTEGER DEFAULT 0,                    -- 显示排序

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_subscription_plans_plan_type
        CHECK (plan_type IN ('free', 'paid')),
    CONSTRAINT chk_subscription_plans_positive_limits
        CHECK (
            (max_files_per_month IS NULL OR max_files_per_month > 0) AND
            (max_storage_gb IS NULL OR max_storage_gb > 0) AND
            (max_api_calls_per_month IS NULL OR max_api_calls_per_month > 0) AND
            (max_file_size_mb IS NULL OR max_file_size_mb > 0) AND
            (max_knowledge_bases IS NULL OR max_knowledge_bases > 0) AND
            (max_api_keys IS NULL OR max_api_keys > 0)
        )
);

-- ================================
-- 用户订阅表 (User Subscriptions)
-- ================================

-- 用户订阅表
CREATE TABLE IF NOT EXISTS unifiles.user_subscriptions (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('sub_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES unifiles.subscription_plans(id),

    -- 订阅状态
    status TEXT DEFAULT 'active',                    -- 'active', 'cancelled', 'expired', 'suspended', 'trial'
    billing_cycle TEXT DEFAULT 'monthly',            -- 'monthly', 'yearly', 'lifetime'

    -- 时间信息
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    current_period_start TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    current_period_end TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    trial_end_at TIMESTAMPTZ,

    -- 支付信息（Stripe集成）
    stripe_subscription_id TEXT UNIQUE,              -- Stripe订阅ID
    stripe_customer_id TEXT,                         -- Stripe客户ID
    stripe_price_id TEXT,                            -- Stripe价格ID

    -- 配额使用情况（本周期内）
    usage_this_period JSONB DEFAULT '{}',            -- {"files_uploaded": 45, "api_calls": 1200, "storage_used_gb": 2.5}

    -- 自动续费
    auto_renew BOOLEAN DEFAULT TRUE,                 -- 是否自动续费

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_user_subscriptions_status
        CHECK (status IN ('active', 'cancelled', 'expired', 'suspended', 'trial')),
    CONSTRAINT chk_user_subscriptions_billing_cycle
        CHECK (billing_cycle IN ('monthly', 'yearly', 'lifetime')),

    -- 索引
    CONSTRAINT uq_user_subscriptions_stripe_subscription
        UNIQUE (stripe_subscription_id)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON unifiles.user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_plan_id ON unifiles.user_subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON unifiles.user_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_period_end ON unifiles.user_subscriptions(current_period_end);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe_customer ON unifiles.user_subscriptions(stripe_customer_id);

-- ================================
-- 订阅历史表 (Subscription History)
-- ================================

-- 订阅历史表
CREATE TABLE IF NOT EXISTS unifiles.subscription_history (
    -- 主键标识
    id TEXT PRIMARY KEY DEFAULT ('subhist_' || encode(gen_random_bytes(16), 'hex')),
    user_id TEXT NOT NULL REFERENCES unifiles.users(id) ON DELETE CASCADE,
    subscription_id TEXT NOT NULL,                   -- 可能指向已删除的订阅

    -- 事件信息
    event_type TEXT NOT NULL,                        -- 'created', 'upgraded', 'downgraded', 'cancelled', 'renewed', 'expired', 'reactivated'
    from_plan_id TEXT REFERENCES unifiles.subscription_plans(id),
    to_plan_id TEXT REFERENCES unifiles.subscription_plans(id),

    -- 元数据
    metadata JSONB DEFAULT '{}',                     -- 额外的事件信息
    reason TEXT,                                     -- 变更原因

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束
    CONSTRAINT chk_subscription_history_event_type
        CHECK (event_type IN ('created', 'upgraded', 'downgraded', 'cancelled', 'renewed', 'expired', 'reactivated', 'suspended'))
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_subscription_history_user_id ON unifiles.subscription_history(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_history_subscription_id ON unifiles.subscription_history(subscription_id);
CREATE INDEX IF NOT EXISTS idx_subscription_history_created_at ON unifiles.subscription_history(created_at DESC);

-- ================================
-- 触发器 (Triggers)
-- ================================

-- 为 subscription_plans 添加更新时间戳触发器
CREATE TRIGGER trigger_subscription_plans_updated_at
    BEFORE UPDATE ON unifiles.subscription_plans
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- 为 user_subscriptions 添加更新时间戳触发器
CREATE TRIGGER trigger_user_subscriptions_updated_at
    BEFORE UPDATE ON unifiles.user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION unifiles.update_updated_at_column();

-- ================================
-- 订阅管理函数 (Subscription Management Functions)
-- ================================

-- 获取用户当前有效订阅
CREATE OR REPLACE FUNCTION get_user_active_subscription(p_user_id TEXT) RETURNS JSONB AS $$
DECLARE
    subscription RECORD;
    plan RECORD;
    result JSONB;
BEGIN
    -- 查找用户的活跃订阅
    SELECT * INTO subscription
    FROM unifiles.user_subscriptions
    WHERE user_id = p_user_id
      AND status = 'active'
      AND (current_period_end IS NULL OR current_period_end > CURRENT_TIMESTAMP)
    ORDER BY current_period_start DESC
    LIMIT 1;

    -- 如果没有活跃订阅，返回免费套餐
    IF subscription IS NULL THEN
        SELECT * INTO plan
        FROM unifiles.subscription_plans
        WHERE plan_name = 'free'
        LIMIT 1;

        RETURN jsonb_build_object(
            'has_subscription', false,
            'plan_name', 'free',
            'plan_details', row_to_json(plan)
        );
    END IF;

    -- 获取套餐详情
    SELECT * INTO plan
    FROM unifiles.subscription_plans
    WHERE id = subscription.plan_id;

    RETURN jsonb_build_object(
        'has_subscription', true,
        'subscription', row_to_json(subscription),
        'plan', row_to_json(plan)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 创建订阅
CREATE OR REPLACE FUNCTION create_subscription(
    p_user_id TEXT,
    p_plan_id TEXT,
    p_billing_cycle TEXT DEFAULT 'monthly',
    p_trial_days INTEGER DEFAULT NULL,
    p_stripe_customer_id TEXT DEFAULT NULL,
    p_stripe_subscription_id TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    new_subscription_id TEXT;
    period_end TIMESTAMPTZ;
    trial_end TIMESTAMPTZ;
BEGIN
    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM unifiles.users WHERE id = p_user_id) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'user_not_found',
            'message', 'User does not exist'
        );
    END IF;

    -- 检查套餐是否存在且可用
    IF NOT EXISTS (SELECT 1 FROM unifiles.subscription_plans WHERE id = p_plan_id AND is_active = true) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'plan_not_found',
            'message', 'Subscription plan not found or inactive'
        );
    END IF;

    -- 计算周期结束时间
    IF p_billing_cycle = 'monthly' THEN
        period_end := CURRENT_TIMESTAMP + INTERVAL '1 month';
    ELSIF p_billing_cycle = 'yearly' THEN
        period_end := CURRENT_TIMESTAMP + INTERVAL '1 year';
    ELSIF p_billing_cycle = 'lifetime' THEN
        period_end := NULL;  -- 永久订阅
    END IF;

    -- 计算试用结束时间
    IF p_trial_days IS NOT NULL AND p_trial_days > 0 THEN
        trial_end := CURRENT_TIMESTAMP + (p_trial_days || ' days')::INTERVAL;
    END IF;

    -- 生成订阅ID
    new_subscription_id := 'sub_' || encode(gen_random_bytes(16), 'hex');

    -- 插入新订阅
    INSERT INTO unifiles.user_subscriptions (
        id, user_id, plan_id, status, billing_cycle,
        current_period_start, current_period_end, trial_end_at,
        stripe_customer_id, stripe_subscription_id
    ) VALUES (
        new_subscription_id, p_user_id, p_plan_id,
        CASE WHEN trial_end IS NOT NULL THEN 'trial' ELSE 'active' END,
        p_billing_cycle,
        CURRENT_TIMESTAMP, period_end, trial_end,
        p_stripe_customer_id, p_stripe_subscription_id
    );

    -- 记录订阅历史
    INSERT INTO unifiles.subscription_history (
        user_id, subscription_id, event_type, to_plan_id,
        metadata
    ) VALUES (
        p_user_id, new_subscription_id, 'created', p_plan_id,
        jsonb_build_object(
            'billing_cycle', p_billing_cycle,
            'trial_days', p_trial_days
        )
    );

    RETURN jsonb_build_object(
        'success', true,
        'subscription_id', new_subscription_id,
        'message', 'Subscription created successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 取消订阅
CREATE OR REPLACE FUNCTION cancel_subscription(
    p_subscription_id TEXT,
    p_reason TEXT DEFAULT NULL,
    p_immediate BOOLEAN DEFAULT FALSE
) RETURNS JSONB AS $$
DECLARE
    subscription RECORD;
BEGIN
    -- 获取订阅信息
    SELECT * INTO subscription
    FROM unifiles.user_subscriptions
    WHERE id = p_subscription_id;

    IF subscription IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'subscription_not_found',
            'message', 'Subscription not found'
        );
    END IF;

    IF subscription.status = 'cancelled' THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'already_cancelled',
            'message', 'Subscription already cancelled'
        );
    END IF;

    -- 更新订阅状态
    IF p_immediate THEN
        -- 立即取消
        UPDATE unifiles.user_subscriptions
        SET status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            current_period_end = CURRENT_TIMESTAMP,
            auto_renew = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = p_subscription_id;
    ELSE
        -- 周期结束后取消
        UPDATE unifiles.user_subscriptions
        SET status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP,
            auto_renew = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = p_subscription_id;
    END IF;

    -- 记录订阅历史
    INSERT INTO unifiles.subscription_history (
        user_id, subscription_id, event_type, from_plan_id,
        reason, metadata
    ) VALUES (
        subscription.user_id, p_subscription_id, 'cancelled', subscription.plan_id,
        p_reason, jsonb_build_object('immediate', p_immediate)
    );

    RETURN jsonb_build_object(
        'success', true,
        'message', 'Subscription cancelled successfully'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================
-- 初始化默认订阅套餐
-- ================================

-- 插入免费套餐
INSERT INTO unifiles.subscription_plans (
    id, plan_name, plan_type, display_name, description,
    max_files_per_month, max_storage_gb, max_api_calls_per_month,
    max_file_size_mb, max_knowledge_bases, max_api_keys,
    rate_limit_per_hour, rate_limit_per_day,
    features, price_monthly_usd, price_yearly_usd,
    is_active, is_public, sort_order
) VALUES (
    'plan_free',
    'free',
    'free',
    'Free Plan',
    'Perfect for individuals getting started with Unifiles',
    100,              -- max_files_per_month
    5,                -- max_storage_gb
    1000,             -- max_api_calls_per_month
    10,               -- max_file_size_mb
    3,                -- max_knowledge_bases
    2,                -- max_api_keys
    100,              -- rate_limit_per_hour
    1000,             -- rate_limit_per_day
    '{"ocr": false, "ai_extraction": false, "priority_support": false, "api_access": true}'::JSONB,
    0.00,
    0.00,
    true,
    true,
    1
) ON CONFLICT (plan_name) DO NOTHING;

-- 插入专业版套餐
INSERT INTO unifiles.subscription_plans (
    id, plan_name, plan_type, display_name, description,
    max_files_per_month, max_storage_gb, max_api_calls_per_month,
    max_file_size_mb, max_knowledge_bases, max_api_keys,
    rate_limit_per_hour, rate_limit_per_day,
    features, price_monthly_usd, price_yearly_usd,
    is_active, is_public, sort_order
) VALUES (
    'plan_pro',
    'pro',
    'paid',
    'Professional Plan',
    'For power users and small teams',
    10000,            -- max_files_per_month
    100,              -- max_storage_gb
    100000,           -- max_api_calls_per_month
    100,              -- max_file_size_mb
    50,               -- max_knowledge_bases
    10,               -- max_api_keys
    1000,             -- rate_limit_per_hour
    10000,            -- rate_limit_per_day
    '{"ocr": true, "ai_extraction": true, "priority_support": true, "api_access": true, "webhooks": true}'::JSONB,
    29.00,
    290.00,
    true,
    true,
    2
) ON CONFLICT (plan_name) DO NOTHING;

-- 插入企业版套餐
INSERT INTO unifiles.subscription_plans (
    id, plan_name, plan_type, display_name, description,
    max_files_per_month, max_storage_gb, max_api_calls_per_month,
    max_file_size_mb, max_knowledge_bases, max_api_keys,
    rate_limit_per_hour, rate_limit_per_day,
    features, price_monthly_usd, price_yearly_usd,
    is_active, is_public, sort_order
) VALUES (
    'plan_enterprise',
    'enterprise',
    'paid',
    'Enterprise Plan',
    'For large teams and organizations with custom needs',
    NULL,             -- 无限制
    NULL,             -- 无限制
    NULL,             -- 无限制
    1000,             -- max_file_size_mb
    NULL,             -- 无限制
    NULL,             -- 无限制
    10000,            -- rate_limit_per_hour
    100000,           -- rate_limit_per_day
    '{"ocr": true, "ai_extraction": true, "priority_support": true, "api_access": true, "webhooks": true, "custom_integrations": true, "sla": true}'::JSONB,
    299.00,
    2990.00,
    true,
    true,
    3
) ON CONFLICT (plan_name) DO NOTHING;
