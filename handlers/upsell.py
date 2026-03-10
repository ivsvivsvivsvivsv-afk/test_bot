"""
Upsell handler: «Разбор бизнеса» после регистрации на воркшоп.

Flow:
- show_upsell_if_available() — единая точка входа (contacts, arena)
- try_hold_slot → create_payment → кнопки [💳 Перейти к оплате] [✅ Я оплатил]
- [❌ Пропустить] → release_hold → FINAL
"""

from __future__ import annotations

import logging

import asyncpg
from aiogram import F, Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from redis.asyncio import Redis

from keyboards.inline import CB, remove_keyboard
from utils.config_db import get_config
from services.payment_service import (
    cleanup_upsell_messages,
    create_payment,
    get_remaining_slots,
    release_hold,
    store_upsell_message,
    try_hold_slot,
)
from services.quest_service import log_event
from utils.content_manager import ContentManager

logger = logging.getLogger(__name__)
router = Router(name="upsell")


# ── Keyboards ──────────────────────────────────────────────────────────────


def _upsell_pay_kb(price: str) -> InlineKeyboardMarkup:
    b = [
        [InlineKeyboardButton(text=f"💳 Оплатить {price} ₽", callback_data=f"{CB.UPSELL}:pay")],
        [InlineKeyboardButton(text="❌ Пропустить", callback_data=f"{CB.UPSELL}:skip")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=b)


def _upsell_payment_kb(url: str) -> InlineKeyboardMarkup:
    b = [
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"{CB.UPSELL}:check")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=b)


# ── Public entry point ─────────────────────────────────────────────────────


async def show_upsell_if_available(
    bot: Bot,
    user_id: int,
    chat_id: int,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> bool:
    """
    Единая функция показа upsell.
    Вызывается после workshop_registered = TRUE (из contacts, arena).

    Returns True если upsell показан, False если пропущен (нет мест / уже показывали).
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT upsell_shown FROM users WHERE user_id = $1",
                user_id,
            )
            if row and row["upsell_shown"]:
                logger.debug("Upsell already shown for user %s", user_id)
                return False

        remaining = await get_remaining_slots(pool, redis_conn)
        if remaining <= 0:
            logger.info("No upsell slots for user %s", user_id)
            return False

        held = await try_hold_slot(pool, redis_conn, user_id)
        if not held:
            logger.info("Could not hold slot for user %s", user_id)
            return False

        cfg = await get_config(pool)
        price = cfg.get("upsell_price", "5000")
        total = cfg.get("upsell_total_slots", "10")

        text = ContentManager.get("upsell_offer", slots=f"{remaining}/{total}", price=price)

        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=_upsell_pay_kb(price),
        )

        await store_upsell_message(redis_conn, user_id, chat_id, msg.message_id)

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET upsell_shown = TRUE WHERE user_id = $1",
                user_id,
            )

        await log_event(pool, user_id, "upsell_shown", {"slots": remaining})
        logger.info("Upsell shown to user %s, remaining=%s", user_id, remaining)
        return True
    except Exception:
        logger.exception("show_upsell_if_available failed for user %s", user_id)
        await release_hold(redis_conn, user_id)
        return False


# ── Handlers ───────────────────────────────────────────────────────────────


@router.callback_query(F.data == f"{CB.UPSELL}:pay")
async def cb_upsell_pay(
    callback: CallbackQuery,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """[💳 Оплатить] — hold уже установлен при показе, создаём платёж."""
    user_id = callback.from_user.id

    result = await create_payment(pool, redis_conn, user_id)

    if "error" in result:
        if result["error"] == "no_slots":
            try:
                await callback.message.edit_text(
                    ContentManager.get_raw("upsell_no_slots"),
                    reply_markup=None,
                )
            except TelegramBadRequest:
                pass
            await callback.answer()
        elif result["error"] == "payments_disabled":
            await callback.answer("Платежи временно недоступны.", show_alert=True)
        else:
            await callback.answer("Ошибка создания платежа. Попробуйте позже.", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(
            reply_markup=_upsell_payment_kb(result["url"]),
        )
    except TelegramBadRequest:
        pass

    await log_event(pool, user_id, "payment_created", {"payment_id": result["payment_id"]})
    await callback.answer("Переходите к оплате!")


@router.callback_query(F.data == f"{CB.UPSELL}:skip")
async def cb_upsell_skip(
    callback: CallbackQuery,
    redis_conn: Redis,
) -> None:
    """[❌ Пропустить] — release hold, FINAL."""
    user_id = callback.from_user.id
    await release_hold(redis_conn, user_id)

    try:
        await callback.message.edit_text(
            ContentManager.get_raw("upsell_skipped"),
            reply_markup=None,
        )
    except TelegramBadRequest:
        pass

    await callback.answer("Хорошо, до встречи!")


@router.callback_query(F.data == f"{CB.UPSELL}:check")
async def cb_upsell_check(
    callback: CallbackQuery,
    pool: asyncpg.Pool,
) -> None:
    """[✅ Я оплатил] — проверка статуса в БД."""
    user_id = callback.from_user.id
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT status FROM payments
            WHERE user_id = $1 AND offer_type = 'business_review'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    if row and row["status"] == "succeeded":
        try:
            await callback.message.edit_text(
                ContentManager.get_raw("payment_success"),
                reply_markup=None,
            )
        except TelegramBadRequest:
            pass
        await callback.answer("Оплата подтверждена!")
    else:
        await callback.answer(
            "Платёж ещё не подтверждён. Подождите 1–2 минуты.",
            show_alert=True,
        )
