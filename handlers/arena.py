"""
Arena (hackathon) flow handler.

Flow: intro → 3 qualification questions → contact collection → quest offer.
Arena is played ONCE per user; revisiting shows "already registered".
Qualification answers + scoring are persisted to PostgreSQL for CRM/sales.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import asyncpg
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from keyboards.inline import (
    CB,
    get_arena_contacts_keyboard,
    get_arena_intro_keyboard,
    get_arena_q1_keyboard,
    get_arena_q2_keyboard,
    get_arena_q3_keyboard,
    get_arena_quest_offer_keyboard,
    get_start_keyboard,
    remove_keyboard,
)
from services.quest_service import get_user, log_event, touch_activity
from utils.content_manager import ContentManager
from utils.notifications import (
    EXPERIENCE_LABELS,
    GOAL_LABELS,
    TOOLS_LABELS,
    notify_arena_lead,
)
from utils.validation import validate_phone

logger = logging.getLogger(__name__)
router = Router(name="arena")


# ── FSM states ──────────────────────────────────────────────


class ArenaStates(StatesGroup):
    INTRO = State()
    QUESTION_1 = State()
    QUESTION_2 = State()
    QUESTION_3 = State()
    QUALIFICATION_RESULT = State()
    ARENA_PHONE = State()
    ARENA_DONE = State()


# ── Helpers ─────────────────────────────────────────────────


async def _safe_remove_kb(msg: Message) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest:
        pass


async def _save_arena_data(
    pool: asyncpg.Pool,
    user_id: int,
    phone: str | None,
    q1: str,
    q2: str,
    q3: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET
                phone = COALESCE($2, phone),
                arena_registered = TRUE,
                arena_q1_experience = $3,
                arena_q2_tools = $4,
                arena_q3_goal = $5
            WHERE user_id = $1
            """,
            user_id, phone, q1, q2, q3,
        )


# ── Entry point (called from start handler) ────────────────


@router.callback_query(F.data == f"{CB.START}:arena")
async def cb_arena_intro(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s → arena", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await touch_activity(redis_conn, user_id)
    await log_event(pool, user_id, "arena_start")

    row = await get_user(pool, user_id)
    if row and row.get("arena_registered"):
        await callback.message.answer(
            ContentManager.get_raw("arena_already_registered"),
        )
        return

    await state.set_state(ArenaStates.INTRO)
    await callback.message.answer(
        ContentManager.get_raw("arena_intro"),
        reply_markup=get_arena_intro_keyboard(),
    )


# ── Participate button → question 1 ────────────────────────


@router.callback_query(F.data == f"{CB.ARENA}:participate")
async def cb_arena_participate(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s arena participate", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await log_event(pool, user_id, "arena_participate")
    await touch_activity(redis_conn, user_id)

    await state.set_state(ArenaStates.QUESTION_1)
    await callback.message.answer(
        ContentManager.get_raw("arena_q1"),
        reply_markup=get_arena_q1_keyboard(),
    )


# ── Question 1 → Question 2 ────────────────────────────────


@router.callback_query(F.data.startswith(f"{CB.ARENA}:q1:"))
async def cb_arena_q1(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    answer = callback.data.split(":")[-1]
    logger.info("User %s arena q1=%s", user_id, answer)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.update_data(arena_q1=answer)
    await log_event(pool, user_id, "arena_q1_answered", {"answer": answer})
    await touch_activity(redis_conn, user_id)

    await state.set_state(ArenaStates.QUESTION_2)
    await callback.message.answer(
        ContentManager.get_raw("arena_q2"),
        reply_markup=get_arena_q2_keyboard(),
    )


# ── Question 2 → Question 3 ────────────────────────────────


@router.callback_query(F.data.startswith(f"{CB.ARENA}:q2:"))
async def cb_arena_q2(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    answer = callback.data.split(":")[-1]
    logger.info("User %s arena q2=%s", user_id, answer)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.update_data(arena_q2=answer)
    await log_event(pool, user_id, "arena_q2_answered", {"answer": answer})
    await touch_activity(redis_conn, user_id)

    await state.set_state(ArenaStates.QUESTION_3)
    await callback.message.answer(
        ContentManager.get_raw("arena_q3"),
        reply_markup=get_arena_q3_keyboard(),
    )


# ── Question 3 → Qualification result ──────────────────────


@router.callback_query(F.data.startswith(f"{CB.ARENA}:q3:"))
async def cb_arena_q3(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    answer = callback.data.split(":")[-1]
    logger.info("User %s arena q3=%s", user_id, answer)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.update_data(arena_q3=answer)
    await log_event(pool, user_id, "arena_q3_answered", {"answer": answer})
    await touch_activity(redis_conn, user_id)

    data = await state.get_data()
    q1 = data.get("arena_q1", "beginner")
    q2 = data.get("arena_q2", "chat")
    q3 = answer

    await state.set_state(ArenaStates.QUALIFICATION_RESULT)
    await callback.message.answer(
        ContentManager.get(
            "arena_qualification_result",
            experience=EXPERIENCE_LABELS.get(q1, q1),
            tools=TOOLS_LABELS.get(q2, q2),
            goal=GOAL_LABELS.get(q3, q3),
        ),
        reply_markup=get_arena_contacts_keyboard(),
    )


# ── Contacts button → phone input ──────────────────────────


@router.callback_query(F.data == f"{CB.ARENA}:contacts")
async def cb_arena_contacts_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await _safe_remove_kb(callback.message)
    await callback.answer()

    await state.set_state(ArenaStates.ARENA_PHONE)
    await callback.message.answer(
        ContentManager.get_raw("contact_phone_request"),
    )


# ── Phone input ─────────────────────────────────────────────


@router.message(ArenaStates.ARENA_PHONE, F.text, ~F.text.startswith("/"))
async def process_arena_phone(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = message.from_user.id
    phone_input = (message.text or "").strip()

    result = validate_phone(phone_input)
    if not result.is_valid:
        await message.answer(
            f"❌ {result.error}\n\n"
            f"{ContentManager.get_raw('contact_phone_format_hint')}",
        )
        return

    logger.info("User %s arena phone validated", user_id)
    await state.update_data(phone=result.normalized_value)

    data = await state.get_data()
    phone = result.normalized_value
    q1 = data.get("arena_q1", "beginner")
    q2 = data.get("arena_q2", "chat")
    q3 = data.get("arena_q3", "bot")

    await _save_arena_data(pool, user_id, phone, q1, q2, q3)
    await log_event(pool, user_id, "contact_phone", {"phone": phone})
    await log_event(pool, user_id, "arena_registered")
    await touch_activity(redis_conn, user_id)

    await notify_arena_lead(
        bot=message.bot,
        user_id=user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        phone=phone,
        q1=q1,
        q2=q2,
        q3=q3,
    )

    await state.set_state(ArenaStates.ARENA_DONE)
    await message.answer(
        ContentManager.get_raw("arena_contacts_saved"),
        reply_markup=get_arena_quest_offer_keyboard(),
    )


# ── Quest offer: accept → redirect to quest ─────────────────


@router.callback_query(F.data == f"{CB.ARENA}:to_quest")
async def cb_arena_to_quest(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s arena → quest", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await log_event(pool, user_id, "arena_to_quest")
    await state.clear()

    from handlers.quest import show_class_selection
    await show_class_selection(callback.message, state, pool, user_id)


# ── Quest offer: decline ────────────────────────────────────


@router.callback_query(F.data == f"{CB.ARENA}:decline_quest")
async def cb_arena_decline_quest(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s arena declined quest", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await log_event(pool, user_id, "arena_declined_quest")
    await state.clear()

    await callback.message.answer(
        ContentManager.get_raw("arena_done"),
    )


# ── Back button → start menu ───────────────────────────────


@router.callback_query(F.data == f"{CB.ARENA}:back")
async def cb_arena_back(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    logger.info("User %s arena → back", callback.from_user.id)

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.clear()

    await callback.message.answer(
        ContentManager.get("welcome"),
        reply_markup=get_start_keyboard(),
    )
