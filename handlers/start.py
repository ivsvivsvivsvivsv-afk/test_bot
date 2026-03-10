"""
/start handler and initial flow.

Key decisions:
- /restart is REMOVED for regular users (quest is one-shot).
- Returning users who completed the quest see a "workshop?" prompt.
- Returning users whose quest is in-progress resume from the saved FSM state;
  if FSM data is lost (Redis eviction) we rebuild it from PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import asyncpg
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from keyboards.inline import (
    CB,
    get_continue_keyboard,
    get_resume_keyboard,
    get_start_keyboard,
    get_welcome_back_keyboard,
    remove_keyboard,
    url_button,
)
from utils.media_ids import get_file_id
from services.quest_service import (
    get_or_create_user,
    get_user,
    log_event,
    touch_activity,
    update_quest_state,
)
from utils.content_manager import ContentManager
logger = logging.getLogger(__name__)
router = Router(name="start")


# ── Helpers ─────────────────────────────────────────────────


def _first_name(user) -> str:
    return user.first_name or "Воин"


async def _safe_remove_kb(msg: Message) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest:
        pass


# Map PG quest_state → FSM state name for resume logic
_PG_TO_FSM: Dict[str, str] = {
    "class_selected": "QuestStates:CLASS_SELECTION",
    "weapon_selected": "QuestStates:WEAPON_SELECTION",
    "round_1": "QuestStates:ROUND_1",
    "round_1_done": "QuestStates:ROUND_1_RESULT",
    "round_2": "QuestStates:ROUND_2",
    "round_2_done": "QuestStates:ROUND_2_RESULT",
    "round_3": "QuestStates:ROUND_3",
    "round_3_done": "QuestStates:ROUND_3_RESULT",
}


async def _try_restore_fsm(
    state: FSMContext,
    user_row: Dict[str, Any],
) -> bool:
    """
    Attempt to rebuild FSM data from PostgreSQL backup.
    Returns True if there is an in-progress quest to resume.
    """
    pg_state = user_row.get("quest_state", "start")
    if pg_state in ("start", "completed") or user_row.get("quest_completed"):
        return False

    fsm_data: Dict[str, Any] = {}
    if user_row.get("player_class"):
        fsm_data["hero_class"] = user_row["player_class"]
    if user_row.get("weapon"):
        fsm_data["weapon"] = user_row["weapon"]
    fsm_data["current_round"] = user_row.get("round_number") or 0
    fsm_data["score"] = user_row.get("score") or 0

    await state.update_data(**fsm_data)

    fsm_state_name = _PG_TO_FSM.get(pg_state)
    if fsm_state_name:
        await state.set_state(fsm_state_name)

    return True


# ── /start ──────────────────────────────────────────────────


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user = message.from_user
    user_id = user.id

    args = message.text.split(maxsplit=1)
    source = args[1] if len(args) > 1 else None

    logger.info("User %s /start, source=%s", user_id, source)

    existing = await get_user(pool, user_id)

    if existing is None:
        await get_or_create_user(
            pool,
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            source=source,
        )
        await log_event(pool, user_id, "bot_start", {"source": source})
        await touch_activity(redis_conn, user_id)

        img_start = get_file_id("img_start")
        welcome = ContentManager.get("welcome")
        if img_start:
            await message.answer_photo(
                photo=img_start,
                caption=welcome,
                reply_markup=get_start_keyboard(),
            )
        else:
            await message.answer(welcome, reply_markup=get_start_keyboard())
        return

    # ── Returning user ──────────────────────────────────────
    await touch_activity(redis_conn, user_id)
    first = _first_name(user)

    if existing.get("quest_completed"):
        await message.answer(
            ContentManager.get("welcome_back_completed", first_name=first),
            reply_markup=get_welcome_back_keyboard(),
        )
        return

    # Quest in progress — try to restore FSM
    has_progress = await _try_restore_fsm(state, existing)
    if has_progress:
        await message.answer(
            ContentManager.get("welcome_back_in_progress", first_name=first),
            reply_markup=get_resume_keyboard(),
        )
        return

    # Edge case: user exists but quest_state='start' (registered but never started)
    await state.clear()
    img_start = get_file_id("img_start")
    welcome = ContentManager.get("welcome")
    if img_start:
        await message.answer_photo(
            photo=img_start,
            caption=welcome,
            reply_markup=get_start_keyboard(),
        )
    else:
        await message.answer(welcome, reply_markup=get_start_keyboard())


# ── Begin quest button ──────────────────────────────────────


@router.callback_query(F.data == f"{CB.START}:begin_quest")
async def cb_begin_quest(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s begin_quest", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()

    await log_event(pool, user_id, "quest_start")
    await update_quest_state(pool, user_id, "quest_intro")

    quest_intro = ContentManager.get("quest_intro")
    img_prepare = get_file_id("img_prepare")
    if img_prepare:
        await callback.message.answer_photo(
            photo=img_prepare,
            caption=quest_intro,
            reply_markup=get_continue_keyboard(),
        )
    else:
        await callback.message.answer(
            quest_intro,
            reply_markup=get_continue_keyboard(),
        )


# ── Continue → class selection ──────────────────────────────


@router.callback_query(F.data == f"{CB.START}:continue")
async def cb_continue_to_class(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    logger.info("User %s → class selection", callback.from_user.id)

    await _safe_remove_kb(callback.message)
    await callback.answer()

    from handlers.quest import show_class_selection

    await show_class_selection(callback.message, state, pool, callback.from_user.id)


# ── About course ────────────────────────────────────────────


@router.callback_query(F.data == f"{CB.START}:about_course")
async def cb_about_course(callback: CallbackQuery) -> None:
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await callback.message.answer(
        ContentManager.get("about_course"),
        reply_markup=get_start_keyboard(),
    )


# ── Generator (redirect to external bot) ─────────────────────


@router.callback_query(F.data == f"{CB.START}:generator")
async def cb_generator(callback: CallbackQuery) -> None:
    from config import GENERATOR_BOT_URL

    await _safe_remove_kb(callback.message)
    await callback.answer()
    await callback.message.answer(
        ContentManager.get_raw("generator_info"),
        reply_markup=url_button("🎬 Открыть Генератор", GENERATOR_BOT_URL),
    )


# ── /help ───────────────────────────────────────────────────


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(ContentManager.get("help"))


# ── /status ─────────────────────────────────────────────────


@router.message(Command("status"))
async def cmd_status(message: Message, pool: asyncpg.Pool) -> None:
    user_id = message.from_user.id
    row = await get_user(pool, user_id)

    if not row:
        await message.answer("Вы ещё не начали квест. Нажмите /start")
        return

    parts: list[str] = []
    if row.get("player_class"):
        parts.append(f"🎭 Класс: {row['player_class']}")
    if row.get("weapon"):
        parts.append(f"⚔️ Оружие: {row['weapon']}")
    if row.get("round_number"):
        parts.append(f"🎯 Раунд: {row['round_number']}/3")
    if row.get("score") is not None:
        parts.append(f"⭐ Очки: {row['score']}")
    if row.get("quest_completed"):
        parts.append("✅ Квест пройден!")
    if not parts:
        parts.append("Квест ещё не начат")

    await message.answer(f"<b>📊 Ваш статус:</b>\n\n" + "\n".join(parts))
