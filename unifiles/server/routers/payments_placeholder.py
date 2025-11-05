"""
支付占位符实现 - MVP阶段手动激活订阅
等有真实付费用户后再集成Stripe
"""

from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException
from loguru import logger

from unifiles.server.schemas import StandardResponse
from unifiles.server.routers.api_keys import get_user_context
from unifiles.config import settings


router = APIRouter(prefix="/payments", tags=["Payments (Placeholder)"])


# ===== POST /payments/checkout - 创建支付会话（占位符）=====

@router.post("/checkout", response_model=dict)
async def create_checkout_placeholder(
    plan_id: str = Body(..., description="订阅套餐ID"),
    billing_cycle: str = Body("monthly", description="计费周期: monthly/yearly"),
    user_context: dict = Depends(get_user_context),
):
    """
    创建支付会话（占位符实现）

    当前实现：返回一个待支付的订单，需要管理员手动激活

    正式版本：将集成Stripe创建checkout session
    """
    try:
        user_id = user_context["user_id"]

        # Create pg_config dict from settings
        pg_config = {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "user": settings.database.user,
            "password": settings.database.password,
        }

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                # 验证套餐存在
                plan = await conn.fetchrow(
                    "SELECT * FROM unifiles.subscription_plans WHERE id = $1 AND is_active = TRUE",
                    plan_id
                )

                if not plan:
                    raise HTTPException(status_code=404, detail="Subscription plan not found")

                # 计算价格
                price = plan['price_monthly_usd'] if billing_cycle == 'monthly' else plan['price_yearly_usd']

                # 创建待支付订单（使用billing_invoices表）
                invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{user_id[:8]}"

                invoice_id = await conn.fetchval("""
                    INSERT INTO unifiles.billing_invoices (
                        user_id,
                        invoice_number,
                        invoice_date,
                        due_date,
                        subtotal_usd,
                        tax_usd,
                        total_usd,
                        status,
                        line_items
                    ) VALUES (
                        $1, $2, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days',
                        $3, $4, $5,
                        'open',  -- 待支付状态
                        $6
                    ) RETURNING id
                """,
                    user_id,
                    invoice_number,
                    price,
                    price * 0.0,  # 暂不计税
                    price,
                    [{"description": f"{plan['plan_name']} Plan - {billing_cycle}", "amount": float(price)}]
                )

                logger.info(f"Created placeholder invoice {invoice_number} for user {user_id}")

                return {
                    "success": True,
                    "message": "Payment order created. Please contact support to complete payment.",
                    "data": {
                        "invoice_id": invoice_id,
                        "invoice_number": invoice_number,
                        "plan_name": plan['plan_name'],
                        "amount": float(price),
                        "currency": "USD",
                        "status": "pending_payment",

                        # 占位符提示
                        "payment_method": "manual",
                        "instructions": f"""
                        请通过以下方式完成支付：
                        1. 联系客服: support@unifiles.com
                        2. 提供账单号: {invoice_number}
                        3. 支付金额: ${price} USD
                        4. 我们将在1个工作日内手动激活您的订阅

                        将来版本将支持自动在线支付（Stripe）
                        """.strip(),

                        # 如果要集成Stripe，这里应该返回：
                        # "checkout_url": "https://checkout.stripe.com/..."
                    }
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating checkout placeholder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== POST /payments/admin/activate - 管理员手动激活订阅 =====

@router.post("/admin/activate", response_model=StandardResponse)
async def admin_activate_subscription(
    invoice_id: str = Body(..., description="账单ID"),
    admin_notes: Optional[str] = Body(None, description="管理员备注"),
    user_context: dict = Depends(get_user_context),
):
    """
    管理员手动激活订阅（占位符实现）

    当前实现：管理员确认收到付款后手动激活

    正式版本：Stripe webhook自动激活

    TODO: 添加管理员权限检查
    """
    try:
        user_id = user_context["user_id"]

        # TODO: 检查是否为管理员
        # if not user_context.get("is_admin"):
        #     raise HTTPException(status_code=403, detail="Admin access required")

        # Create pg_config dict from settings
        pg_config = {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "user": settings.database.user,
            "password": settings.database.password,
        }

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                # 获取账单信息
                invoice = await conn.fetchrow("""
                    SELECT bi.*, u.username
                    FROM unifiles.billing_invoices bi
                    JOIN unifiles.users u ON bi.user_id = u.id
                    WHERE bi.id = $1
                """, invoice_id)

                if not invoice:
                    raise HTTPException(status_code=404, detail="Invoice not found")

                if invoice['status'] == 'paid':
                    raise HTTPException(status_code=400, detail="Invoice already paid")

                # 从line_items中提取plan信息
                line_items = invoice['line_items']
                plan_name = line_items[0]['description'].split(' ')[0]  # 例如: "Pro Plan - monthly"

                # 获取plan_id
                plan = await conn.fetchrow("""
                    SELECT id FROM unifiles.subscription_plans
                    WHERE plan_name = $1
                """, plan_name)

                if not plan:
                    raise HTTPException(status_code=400, detail="Plan not found")

                # 开始事务
                async with conn.transaction():
                    # 1. 更新账单状态为已支付
                    await conn.execute("""
                        UPDATE unifiles.billing_invoices
                        SET status = 'paid',
                            paid_at = CURRENT_TIMESTAMP,
                            payment_method = 'manual',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """, invoice_id)

                    # 2. 调用数据库函数创建订阅
                    subscription_id = await conn.fetchval("""
                        SELECT create_subscription(
                            $1,  -- user_id
                            $2,  -- plan_id
                            'monthly',  -- billing_cycle
                            NULL,  -- trial_days
                            $3   -- metadata
                        )
                    """,
                        invoice['user_id'],
                        plan['id'],
                        {"activated_by": "manual", "invoice_id": invoice_id, "admin_notes": admin_notes}
                    )

                    logger.info(f"Admin activated subscription {subscription_id} for user {invoice['user_id']}")

                    return StandardResponse(
                        success=True,
                        message=f"Subscription activated successfully for user {invoice['username']}",
                        data={
                            "subscription_id": subscription_id,
                            "user_id": invoice['user_id'],
                            "plan_name": plan_name,
                        }
                    )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== GET /payments/invoices - 查看我的账单 =====

@router.get("/invoices", response_model=dict)
async def list_my_invoices(
    limit: int = 20,
    user_context: dict = Depends(get_user_context),
):
    """查看当前用户的所有账单"""
    try:
        user_id = user_context["user_id"]

        # Create pg_config dict from settings
        pg_config = {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "user": settings.database.user,
            "password": settings.database.password,
        }

        async with asyncpg.create_pool(**pg_config) as pool:
            async with pool.acquire() as conn:
                invoices = await conn.fetch("""
                    SELECT id, invoice_number, invoice_date, due_date,
                           total_usd, status, paid_at, line_items,
                           created_at
                    FROM unifiles.billing_invoices
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)

                return {
                    "success": True,
                    "data": {
                        "invoices": [dict(inv) for inv in invoices],
                        "total": len(invoices)
                    }
                }

    except Exception as e:
        logger.error(f"Error listing invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== GET /payments/methods - 支持的支付方式（占位符）=====

@router.get("/methods", response_model=dict)
async def get_payment_methods():
    """
    获取支持的支付方式

    当前：仅手动支付
    未来：Stripe信用卡、支付宝、微信支付等
    """
    return {
        "success": True,
        "data": {
            "available_methods": [
                {
                    "id": "manual",
                    "name": "Manual Payment",
                    "description": "Contact support to complete payment",
                    "enabled": True,
                    "is_placeholder": True
                },
                {
                    "id": "stripe_card",
                    "name": "Credit/Debit Card",
                    "description": "Pay with Stripe (Coming Soon)",
                    "enabled": False,
                    "is_placeholder": True
                },
                {
                    "id": "alipay",
                    "name": "Alipay",
                    "description": "支付宝支付 (Coming Soon)",
                    "enabled": False,
                    "is_placeholder": True
                },
            ],
            "notice": "Automatic payment integration coming soon. Currently using manual activation."
        }
    }


# ===== Stripe Webhook占位符（未来集成时使用）=====

@router.post("/webhooks/stripe")
async def stripe_webhook_placeholder():
    """
    Stripe Webhook处理器（占位符）

    未来实现：
    1. 验证webhook签名
    2. 处理不同的事件类型：
       - checkout.session.completed → 激活订阅
       - invoice.payment_succeeded → 续费成功
       - invoice.payment_failed → 通知用户
       - customer.subscription.deleted → 取消订阅
    """
    return {
        "success": False,
        "message": "Stripe integration not yet implemented. Using manual activation."
    }
