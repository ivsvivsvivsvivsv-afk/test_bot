"""
Payment service: атомарные Lua-скрипты, hold слотов, создание платежей YooKassa.

Architecture (Stage 6):
- Sorted Set для holds: ZADD score=expire_timestamp, member=user_id
- Lua-скрипты для атомарности (Check-Then-Act)
- asyncio.to_thread() для синхронного YooKassa SDK
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

import asyncpg
from redis.asyncio import Redis

from config import YOOKASSA_RETURN_URL, YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID
from utils.config_db import get_config

logger = logging.getLogger(__name__)

# Redis keys
HOLDS_KEY = "upsell:holds"
UPSELL_MSGS_KEY = "upsell:msgs"  # Hash: user_id -> "chat_id:message_id"
HOLD_TTL = 900  # 15 минут

# ── Lua Scripts (атомарные) ────────────────────────────────────────────────

HOLD_SLOT_LUA = """
-- Проверка лимита + установка холда (АТОМАРНО)
local holds_key = KEYS[1]
local user_id = ARGV[1]
local max_slots = tonumber(ARGV[2])
local paid_count = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)
local active_holds = redis.call('ZCARD', holds_key)

if (paid_count + active_holds) >= max_slots then
    return 0
end

redis.call('ZADD', holds_key, now + ttl, user_id)
return 1
"""

CHECK_LIMIT_LUA = """
local holds_key = KEYS[1]
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)
return redis.call('ZCARD', holds_key)
"""


# ── Slot management ────────────────────────────────────────────────────────


async def get_paid_count(pool: asyncpg.Pool, offer_type: str = "business_review") -> int:
    """Подсчёт оплаченных слотов из PostgreSQL."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS cnt
            FROM payments
            WHERE status = 'succeeded' AND offer_type = $1
            """,
            offer_type,
        )
    return row["cnt"] if row else 0


_hold_script = None
_check_script = None


def _get_hold_script(redis_conn: Redis):
    global _hold_script
    if _hold_script is None:
        _hold_script = redis_conn.register_script(HOLD_SLOT_LUA)
    return _hold_script


def _get_check_script(redis_conn: Redis):
    global _check_script
    if _check_script is None:
        _check_script = redis_conn.register_script(CHECK_LIMIT_LUA)
    return _check_script


async def get_active_holds_count(redis_conn: Redis) -> int:
    """Подсчёт активных холдов (Sorted Set, после очистки expired)."""
    try:
        script = _get_check_script(redis_conn)
        return int(await script(keys=[HOLDS_KEY], args=[int(time.time())]))
    except Exception:
        logger.exception("Failed to get active holds count")
        return 0


async def get_remaining_slots(
    pool: asyncpg.Pool,
    redis_conn: Redis,
    offer_type: str = "business_review",
) -> int:
    """
    Подсчёт: total - paid - held.
    total и price из config (PostgreSQL).
    """
    cfg = await get_config(pool)
    total = int(cfg.get("upsell_total_slots", "10"))
    paid = await get_paid_count(pool, offer_type)
    held = await get_active_holds_count(redis_conn)
    return max(0, total - paid - held)


async def try_hold_slot(
    pool: asyncpg.Pool,
    redis_conn: Redis,
    user_id: int,
    offer_type: str = "business_review",
) -> bool:
    """
    Атомарный HOLD через Lua.
    Returns True если место забронировано.
    """
    cfg = await get_config(pool)
    total = int(cfg.get("upsell_total_slots", "10"))
    paid = await get_paid_count(pool, offer_type)
    now = int(time.time())

    try:
        script = _get_hold_script(redis_conn)
        result = await script(
            keys=[HOLDS_KEY],
            args=[str(user_id), str(total), str(paid), str(now), str(HOLD_TTL)],
        )
        return bool(int(result or 0))
    except Exception:
        logger.exception("try_hold_slot failed for user %s", user_id)
        return False


async def release_hold(redis_conn: Redis, user_id: int) -> None:
    """Отпускает бронь (Пропустить / оплата прошла)."""
    try:
        await redis_conn.zrem(HOLDS_KEY, str(user_id))
        logger.debug("Released hold for user %s", user_id)
    except Exception:
        logger.exception("release_hold failed for user %s", user_id)


# ── Payment creation ───────────────────────────────────────────────────────


async def create_payment(
    pool: asyncpg.Pool,
    redis_conn: Redis,
    user_id: int,
    offer_type: str = "business_review",
) -> Dict[str, Any]:
    """
    Создаёт платёж в YooKassa.
    Только если hold установлен (вызывать после try_hold_slot).

    Returns:
        {"url": str, "payment_id": str} или {"error": str}
    """
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        logger.error("YooKassa not configured")
        return {"error": "payments_disabled"}

    remaining = await get_remaining_slots(pool, redis_conn, offer_type)
    if remaining <= 0:
        await release_hold(redis_conn, user_id)
        return {"error": "no_slots"}

    cfg = await get_config(pool)
    price_str = cfg.get("upsell_price", "5000")
    amount = Decimal(price_str)
    idempotence_key = str(uuid.uuid4())

    try:
        from yookassa import Configuration, Payment

        Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

        payment_data = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL,
            },
            "capture": True,
            "description": "НЕЙРО-ЮНИТ: Персональный разбор бизнеса",
            "metadata": {"user_id": str(user_id)},
        }

        payment = await asyncio.to_thread(
            Payment.create,
            payment_data,
            idempotence_key,
        )

        url = payment.confirmation.confirmation_url if payment.confirmation else None
        if not url:
            logger.error("YooKassa returned no confirmation_url")
            await release_hold(redis_conn, user_id)
            return {"error": "create_failed"}

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO payments (user_id, yookassa_payment_id, amount, status, offer_type)
                VALUES ($1, $2, $3, 'pending', $4)
                """,
                user_id,
                payment.id,
                float(amount),
                offer_type,
            )

        logger.info("Payment created: id=%s user=%s", payment.id, user_id)
        return {"url": url, "payment_id": payment.id}
    except Exception:
        logger.exception("create_payment failed for user %s", user_id)
        await release_hold(redis_conn, user_id)
        return {"error": "create_failed"}


# ── Upsell message tracking (cleanup при исчерпании) ───────────────────────


async def store_upsell_message(
    redis_conn: Redis,
    user_id: int,
    chat_id: int,
    message_id: int,
) -> None:
    """Сохранить chat_id:message_id для последующего cleanup."""
    try:
        await redis_conn.hset(
            UPSELL_MSGS_KEY,
            str(user_id),
            f"{chat_id}:{message_id}",
        )
        await redis_conn.expire(UPSELL_MSGS_KEY, 3600)
    except Exception:
        logger.warning("store_upsell_message failed: %s", user_id)


async def cleanup_upsell_messages(bot, redis_conn: Redis) -> None:
    """
    Удалить/обновить все неоплаченные upsell-сообщения.
    Вызывается когда слоты исчерпаны.
    """
    from aiogram.exceptions import TelegramBadRequest

    try:
        msgs = await redis_conn.hgetall(UPSELL_MSGS_KEY)
        if not msgs:
            return

        for user_id_b, value_b in msgs.items():
            try:
                value = value_b.decode() if isinstance(value_b, bytes) else str(value_b)
                parts = value.split(":", 1)
                if len(parts) != 2:
                    continue
                chat_id, msg_id = int(parts[0]), int(parts[1])
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text="😔 К сожалению, все места на персональный разбор уже заняты.",
                )
            except TelegramBadRequest:
                pass
            except Exception as e:
                logger.warning("Cleanup msg error for %s: %s", user_id_b, e)
            finally:
                await redis_conn.hdel(UPSELL_MSGS_KEY, user_id_b)

        logger.info("Cleanup upsell messages completed")
    except Exception:
        logger.exception("cleanup_upsell_messages failed")
