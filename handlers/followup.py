"""
Followup handler — responses to miniquest ПРАВДА/ЛОЖЬ and CTA.

User receives miniquest from worker. Clicks answer -> praise + CTA.
[📝 Записаться] -> contacts flow -> upsell.
[⏭ Позже] -> acknowledge, next day continues.
"""

from __future__ import annotations

import logging

import asyncpg
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from redis.asyncio import Redis

from config import WORKSHOP_URL
from keyboards.inline import CB, get_miniquest_cta_keyboard, remove_keyboard
from utils.content_manager import ContentManager

logger = logging.getLogger(__name__)
router = Router(name="followup")


async def _safe_remove_kb(msg) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith(f"{CB.MINIQUEST}:answer:"))
async def cb_miniquest_answer(
    callback: CallbackQuery,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Handle ПРАВДА/ЛОЖЬ. Show praise + CTA keyboard."""
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return

    user_id = callback.from_user.id
    day = int(parts[2])
    user_said_true = parts[3] == "true"

    key = f"miniquest:pending:{user_id}"
    raw = await redis_conn.get(key)
    if not raw:
        await callback.answer("Задание уже выполнено. Жди следующий миниквест!", show_alert=True)
        return

    decoded = raw.decode() if isinstance(raw, bytes) else raw
    _, is_truth_str = decoded.split("|")
    correct_is_truth = is_truth_str == "1"

    try:
        await redis_conn.delete(key)
    except Exception:
        pass

    is_correct = user_said_true == correct_is_truth
    praise = ContentManager.get_raw("miniquest_correct") if is_correct else ContentManager.get_raw("miniquest_wrong")
    cta = ContentManager.get(f"workshop_cta_day{day}", workshop_url=WORKSHOP_URL)

    await _safe_remove_kb(callback.message)
    await callback.answer("✅ Правильно!" if is_correct else "💪 В следующий раз!")

    text = f"{praise}\n\n{cta}"
    await callback.message.answer(
        text,
        reply_markup=get_miniquest_cta_keyboard(day),
    )


@router.callback_query(F.data.startswith(f"{CB.MINIQUEST}:register:"))
async def cb_miniquest_register(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """[📝 Записаться] -> start contact collection -> upsell."""
    user_id = callback.from_user.id
    await _safe_remove_kb(callback.message)
    await callback.answer()

    try:
        from handlers.contacts import start_contact_collection

        await start_contact_collection(callback.message, state, pool, user_id)
    except Exception as e:
        logger.exception("miniquest register failed for user %s: %s", user_id, e)
        await callback.message.answer(
            "Перейди в меню и нажми /start, чтобы записаться на воркшоп.",
        )


@router.callback_query(F.data.startswith(f"{CB.MINIQUEST}:later:"))
async def cb_miniquest_later(callback: CallbackQuery) -> None:
    """[⏭ Позже] -> acknowledge. Next miniquest tomorrow."""
    await _safe_remove_kb(callback.message)
    await callback.answer("Хорошо! Завтра придёт следующее задание.")
    await callback.message.answer("👌 Понятно. Ждём тебя завтра!")
