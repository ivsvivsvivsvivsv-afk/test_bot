"""
YooKassa webhook handler.

POST /yookassa/webhook — обработка payment.succeeded, payment.canceled.
Идемпотентность: WHERE status != 'succeeded' RETURNING id.
Zombie-protection: auto-refund если paid_count > total_slots.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from aiohttp import web

from utils.config_db import get_config
from utils.content_manager import ContentManager
from utils.notifications import notify_admins

logger = logging.getLogger(__name__)


async def handle_yookassa_webhook(request: web.Request) -> web.Response:
    """
    POST /yookassa/webhook — YooKassa HTTP notifications.
    Всегда возвращаем 200 для подтверждения приёма.
    """
    try:
        body = await request.text()
        data = json.loads(body) if body else {}
    except json.JSONDecodeError as e:
        logger.warning("YooKassa webhook invalid JSON: %s", e)
        return web.Response(status=200)

    event = data.get("event")
    payment_obj = data.get("object") or {}
    payment_id = payment_obj.get("id")

    if not event or not payment_id:
        logger.warning("YooKassa webhook missing event or object.id")
        return web.Response(status=200)

    pool = request.app.get("pool")
    redis_conn = request.app.get("redis_conn")
    bot = request.app.get("bot")

    if not pool or not bot:
        logger.error("YooKassa webhook: app not ready (pool/bot missing)")
        return web.Response(status=200)

    metadata = payment_obj.get("metadata") or {}
    user_id_str = metadata.get("user_id")
    user_id = int(user_id_str) if user_id_str and str(user_id_str).isdigit() else None

    if not user_id:
        logger.warning("YooKassa webhook: no user_id in metadata, payment_id=%s", payment_id)
        return web.Response(status=200)

    if event == "payment.succeeded":
        await _handle_payment_succeeded(
            pool=pool,
            redis_conn=redis_conn,
            bot=bot,
            payment_id=payment_id,
            user_id=user_id,
            payment_obj=payment_obj,
        )
    elif event == "payment.canceled":
        await _handle_payment_canceled(
            pool=pool,
            redis_conn=redis_conn,
            payment_id=payment_id,
        )

    return web.Response(status=200)


async def _handle_payment_succeeded(
    pool,
    redis_conn,
    bot,
    payment_id: str,
    user_id: int,
    payment_obj: Dict[str, Any],
) -> None:
    """Обработка payment.succeeded: идемпотентность, zombie-check, уведомления."""
    from services.payment_service import (
        cleanup_upsell_messages,
        get_paid_count,
        release_hold,
    )
    from services.quest_service import log_event

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE payments
            SET status = 'succeeded', paid_at = NOW()
            WHERE yookassa_payment_id = $1 AND status != 'succeeded'
            RETURNING id
            """,
            payment_id,
        )

    if not row:
        logger.info("YooKassa duplicate webhook (idempotent): payment_id=%s", payment_id)
        return

    if redis_conn:
        await release_hold(redis_conn, user_id)

    cfg = await get_config(pool)
    total_slots = int(cfg.get("upsell_total_slots", "10"))
    paid_count = await get_paid_count(pool, "business_review")

    if paid_count > total_slots:
        await _do_zombie_refund(pool, bot, payment_id, user_id, payment_obj)
        return

    amount = payment_obj.get("amount", {}).get("value", "0")
    await log_event(pool, user_id, "payment_succeeded", {"amount": float(amount)})

    try:
        await bot.send_message(
            chat_id=user_id,
            text=ContentManager.get_raw("payment_success"),
        )
    except Exception:
        logger.warning("Could not send payment success to user %s", user_id)

    await notify_admins(
        bot,
        f"💰 <b>Новая оплата!</b>\n\n"
        f"🆔 User: <code>{user_id}</code>\n"
        f"💳 Payment: {payment_id}\n"
        f"💵 Сумма: {amount} ₽\n"
        f"📊 Осталось мест: {total_slots - paid_count}/{total_slots}",
    )

    if paid_count >= total_slots and redis_conn:
        await cleanup_upsell_messages(bot, redis_conn)


async def _do_zombie_refund(
    pool,
    bot,
    payment_id: str,
    user_id: int,
    payment_obj: Dict[str, Any],
) -> None:
    """Auto-refund при zombie-платеже (перебронирование)."""
    from config import YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        logger.error("Zombie refund: YooKassa not configured")
        return

    try:
        from yookassa import Configuration, Refund

        Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

        amount = payment_obj.get("amount", {})
        await asyncio.to_thread(
            Refund.create,
            {
                "payment_id": payment_id,
                "amount": {"value": amount.get("value", "0"), "currency": "RUB"},
            },
        )

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET status = 'refunded' WHERE yookassa_payment_id = $1",
                payment_id,
            )

        try:
            await bot.send_message(
                chat_id=user_id,
                text=ContentManager.get_raw("payment_refund"),
            )
        except Exception:
            pass

        await notify_admins(
            bot,
            f"⚠️ <b>CRITICAL: auto-refund</b>\n\n"
            f"Zombie-платёж (перебронирование). User: <code>{user_id}</code>, "
            f"Payment: {payment_id}. Деньги возвращены.",
        )
        logger.warning("Zombie refund completed for user %s payment %s", user_id, payment_id)
    except Exception:
        logger.exception("Zombie refund FAILED for user %s", user_id)
        await notify_admins(
            bot,
            f"🚨 <b>CRITICAL: refund failed!</b>\n\n"
            f"User: <code>{user_id}</code>, Payment: {payment_id}. "
            f"Требуется ручной возврат!",
        )


async def _handle_payment_canceled(
    pool,
    redis_conn,
    payment_id: str,
) -> None:
    """Обработка payment.canceled: обновление статуса, release hold."""
    from services.payment_service import release_hold
    from services.quest_service import log_event

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE payments
            SET status = 'canceled'
            WHERE yookassa_payment_id = $1 AND status = 'pending'
            RETURNING user_id
            """,
            payment_id,
        )

    if row:
        await log_event(pool, row["user_id"], "payment_canceled", {"payment_id": payment_id})
    if row and redis_conn:
        user_id = row["user_id"]
        await release_hold(redis_conn, user_id)
        logger.info("Payment canceled: payment_id=%s user_id=%s", payment_id, user_id)
