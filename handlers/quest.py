"""
Quest flow handler: class → weapon → 3 rounds → result → moral.

Design rules:
- User CANNOT restart the quest (no /restart, no "play again" button).
- Quest is played ONCE; returning users see the workshop prompt.
- Every state transition is backed up to PostgreSQL (quest_state column).
- Statements are cached in Redis (see utils.statements).
- Events are logged to the ``events`` table for funnel analytics.
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
    HERO_CLASSES,
    WEAPONS,
    get_answer_keyboard,
    get_class_keyboard,
    get_finish_keyboard,
    get_moral_keyboard,
    get_next_round_keyboard,
    get_weapon_keyboard,
    remove_keyboard,
)
from services.quest_service import (
    complete_quest,
    log_event,
    save_class,
    save_round_result,
    save_round_start,
    save_weapon,
    touch_activity,
    update_quest_state,
)
from utils.content_manager import ContentManager
from utils.media_ids import get_file_id, get_weapon_image
from utils.statements import (
    format_round_result,
    format_statement,
    get_statement_for_round,
)

logger = logging.getLogger(__name__)
router = Router(name="quest")


# ── FSM states ──────────────────────────────────────────────


class QuestStates(StatesGroup):
    CLASS_SELECTION = State()
    WEAPON_SELECTION = State()
    ROUND_1 = State()
    ROUND_1_RESULT = State()
    ROUND_2 = State()
    ROUND_2_RESULT = State()
    ROUND_3 = State()
    ROUND_3_RESULT = State()
    QUEST_RESULTS = State()
    MORAL = State()
    COMPLETED = State()


_ROUND_STATE = {
    1: QuestStates.ROUND_1,
    2: QuestStates.ROUND_2,
    3: QuestStates.ROUND_3,
}
_ROUND_RESULT_STATE = {
    1: QuestStates.ROUND_1_RESULT,
    2: QuestStates.ROUND_2_RESULT,
    3: QuestStates.ROUND_3_RESULT,
}


# ── Helpers ─────────────────────────────────────────────────


async def _safe_remove_kb(msg: Message) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest:
        pass


# ── Class selection (called from start handler) ─────────────


async def show_class_selection(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    user_id: int,
) -> None:
    await state.set_state(QuestStates.CLASS_SELECTION)
    await update_quest_state(pool, user_id, "class_selection")
    text = ContentManager.get("select_class")
    img = get_file_id("img_free_boss")
    if img:
        await message.answer_photo(
            photo=img,
            caption=text,
            reply_markup=get_class_keyboard(),
        )
    else:
        await message.answer(text, reply_markup=get_class_keyboard())


# ── Resume from interrupted quest ───────────────────────────


@router.callback_query(F.data == f"{CB.QUEST}:resume")
async def cb_resume_quest(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Resume the quest from the point where the user left off."""
    user_id = callback.from_user.id
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await touch_activity(redis_conn, user_id)

    data = await state.get_data()
    current_round = data.get("current_round", 0)
    hero_class = data.get("hero_class")
    weapon = data.get("weapon")

    if not hero_class:
        await show_class_selection(callback.message, state, pool, user_id)
        return

    if not weapon:
        await state.set_state(QuestStates.WEAPON_SELECTION)
        text = ContentManager.get(
            "class_selected",
            class_name=HERO_CLASSES[hero_class]["name"],
            class_desc=HERO_CLASSES[hero_class]["desc"],
        )
        img = get_file_id("img_proff")
        if img:
            await callback.message.answer_photo(
                photo=img,
                caption=text,
                reply_markup=get_weapon_keyboard(),
            )
        else:
            await callback.message.answer(text, reply_markup=get_weapon_keyboard())
        return

    # Weapon selected → resume at the next unfinished round
    resume_round = max(current_round, 1)
    await _start_round(callback.message, state, pool, redis_conn, user_id, resume_round)


# ── Select class ────────────────────────────────────────────


@router.callback_query(F.data.startswith(f"{CB.QUEST}:class:"))
async def cb_select_class(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    class_id = callback.data.split(":")[-1]

    if class_id not in HERO_CLASSES:
        await callback.answer("Неизвестный класс", show_alert=True)
        return

    info = HERO_CLASSES[class_id]
    logger.info("User %s class=%s", user_id, class_id)

    await _safe_remove_kb(callback.message)
    await callback.answer(f"Вы выбрали: {info['name']}")

    await state.update_data(hero_class=class_id)
    await save_class(pool, user_id, class_id)
    await log_event(pool, user_id, "class_selected", {"class": class_id})
    await touch_activity(redis_conn, user_id)

    await state.set_state(QuestStates.WEAPON_SELECTION)
    await callback.message.answer(
        ContentManager.get("class_selected", class_name=info["name"], class_desc=info["desc"]),
        reply_markup=get_weapon_keyboard(),
    )


# ── Select weapon ───────────────────────────────────────────


@router.callback_query(F.data.startswith(f"{CB.QUEST}:weapon:"))
async def cb_select_weapon(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    weapon_id = callback.data.split(":")[-1]

    if weapon_id not in WEAPONS:
        await callback.answer("Неизвестное оружие", show_alert=True)
        return

    info = WEAPONS[weapon_id]
    logger.info("User %s weapon=%s", user_id, weapon_id)

    await _safe_remove_kb(callback.message)
    await callback.answer(f"Вы выбрали: {info['name']}")

    await state.update_data(weapon=weapon_id, current_round=1, score=0)
    await save_weapon(pool, user_id, weapon_id)
    await log_event(pool, user_id, "weapon_selected", {"weapon": weapon_id})
    await touch_activity(redis_conn, user_id)

    weapon_text = ContentManager.get("weapon_selected", weapon_name=info["name"], weapon_desc=info["desc"])
    weapon_img = get_weapon_image(weapon_id)
    if weapon_img:
        await callback.message.answer_photo(
            photo=weapon_img,
            caption=weapon_text,
        )
    else:
        await callback.message.answer(weapon_text)

    await _start_round(callback.message, state, pool, redis_conn, user_id, 1)


# ── Round lifecycle ─────────────────────────────────────────


async def _start_round(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
    user_id: int,
    round_num: int,
) -> None:
    data = await state.get_data()
    weapon = data.get("weapon", "other")
    score = data.get("score", 0)

    statement = await get_statement_for_round(weapon, round_num, redis_conn)

    await state.update_data(
        current_round=round_num,
        current_statement_text=statement.text,
        current_statement_is_truth=statement.is_truth,
        current_statement_wisdom=statement.wisdom_prompt,
    )

    await save_round_start(pool, user_id, round_num, statement.text, statement.is_truth)
    await state.set_state(_ROUND_STATE[round_num])

    text = format_statement(statement, round_num, score)
    await message.answer(text, reply_markup=get_answer_keyboard())


# ── Answer ──────────────────────────────────────────────────


@router.callback_query(F.data.startswith(f"{CB.QUEST}:answer:"))
async def cb_answer(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    answer_str = callback.data.split(":")[-1]
    user_said_true = answer_str == "true"

    data = await state.get_data()
    current_round = data.get("current_round", 1)
    is_truth = data.get("current_statement_is_truth", True)
    score = data.get("score", 0)

    is_correct = user_said_true == is_truth

    if is_correct:
        score += 1

    await state.update_data(score=score)

    logger.info(
        "User %s round=%d correct=%s score=%d", user_id, current_round, is_correct, score
    )

    await _safe_remove_kb(callback.message)
    await callback.answer("✅ Правильно!" if is_correct else "❌ Неверно!")

    await save_round_result(pool, user_id, current_round, score)
    await log_event(
        pool,
        user_id,
        "round_completed",
        {"round": current_round, "correct": is_correct, "score": score},
    )
    await touch_activity(redis_conn, user_id)

    from utils.statements import Statement

    stmt = Statement(
        text=data.get("current_statement_text", ""),
        is_truth=is_truth,
        wisdom_prompt=data.get("current_statement_wisdom", ""),
        level=current_round,
    )

    result_text = format_round_result(is_correct, current_round, score, stmt)
    is_last = current_round >= 3
    result_img = get_file_id("img_kill") if is_correct else get_file_id("img_gidratt")

    await state.set_state(_ROUND_RESULT_STATE[current_round])

    if result_img:
        await callback.message.answer_photo(
            photo=result_img,
            caption=result_text,
            reply_markup=get_next_round_keyboard(is_last=is_last),
        )
    else:
        await callback.message.answer(
            result_text,
            reply_markup=get_next_round_keyboard(is_last=is_last),
        )


# ── Next round ──────────────────────────────────────────────


@router.callback_query(F.data == f"{CB.QUEST}:next_round")
async def cb_next_round(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    data = await state.get_data()
    next_round = data.get("current_round", 1) + 1

    logger.info("User %s → round %d", user_id, next_round)

    await _safe_remove_kb(callback.message)
    await callback.answer()

    await _start_round(callback.message, state, pool, redis_conn, user_id, next_round)


# ── Show result ─────────────────────────────────────────────


@router.callback_query(F.data == f"{CB.QUEST}:show_result")
async def cb_show_result(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    data = await state.get_data()
    score = data.get("score", 0)
    weapon = data.get("weapon", "other")
    hero_class = data.get("hero_class", "businessman")
    first_name = callback.from_user.first_name or "Воин"

    logger.info("User %s quest done, score=%d", user_id, score)

    await _safe_remove_kb(callback.message)
    await callback.answer("🏆 Квест завершён!")

    result_map = {3: "perfect", 2: "good", 1: "ok", 0: "bad"}
    emoji_map = {3: "🏆", 2: "🎖️", 1: "🥉", 0: "💪"}

    result_key = f"result_{result_map.get(score, 'bad')}"
    result_text = ContentManager.get(result_key, first_name=first_name)
    result_emoji = emoji_map.get(score, "💪")

    weapon_name = WEAPONS.get(weapon, {}).get("name", weapon)
    class_name = HERO_CLASSES.get(hero_class, {}).get("name", hero_class)

    final_text = ContentManager.get(
        "quest_result_header",
        result_emoji=result_emoji,
        class_name=class_name,
        weapon_name=weapon_name,
        score=str(score),
        result_text=result_text,
    )

    await complete_quest(pool, user_id, score)
    await log_event(pool, user_id, "quest_completed", {"score": score})
    await touch_activity(redis_conn, user_id)
    await state.set_state(QuestStates.QUEST_RESULTS)

    result_img = get_file_id("img_win") if score >= 3 else get_file_id("img_lose")
    if result_img:
        await callback.message.answer_photo(
            photo=result_img,
            caption=final_text,
            reply_markup=get_finish_keyboard(),
        )
    else:
        await callback.message.answer(final_text, reply_markup=get_finish_keyboard())


# ── Get prize (→ moral then contacts) ──────────────────────


@router.callback_query(F.data == f"{CB.QUEST}:get_prize")
async def cb_get_prize(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    user_id = callback.from_user.id
    logger.info("User %s → moral / contacts", user_id)

    await _safe_remove_kb(callback.message)
    await callback.answer()

    current = await state.get_state()

    if current == QuestStates.QUEST_RESULTS.state:
        await state.set_state(QuestStates.MORAL)
        await update_quest_state(pool, user_id, "moral")
        moral_text = ContentManager.get("moral")
        moral_img = get_file_id("img_stark")
        if moral_img:
            await callback.message.answer_photo(
                photo=moral_img,
                caption=moral_text,
                reply_markup=get_moral_keyboard(),
            )
        else:
            await callback.message.answer(moral_text, reply_markup=get_moral_keyboard())
        return

    # Already past moral — transition to contact collection (Stage 5)
    await state.set_state(QuestStates.COMPLETED)
    await update_quest_state(pool, user_id, "completed")

    try:
        from handlers.contacts import start_contact_collection
        await start_contact_collection(callback.message, state, pool, user_id)
    except Exception:
        logger.warning("contacts handler not available, showing fallback", exc_info=True)
        await callback.message.answer(ContentManager.get("contact_intro"))


# ── Workshop shortcut (for returning users) ─────────────────


@router.callback_query(F.data == f"{CB.QUEST}:workshop")
async def cb_workshop(callback: CallbackQuery) -> None:
    from config import WORKSHOP_URL
    from keyboards.inline import get_workshop_keyboard

    await _safe_remove_kb(callback.message)
    await callback.answer()
    moral_text = ContentManager.get("moral")
    moral_img = get_file_id("img_stark")
    if moral_img:
        await callback.message.answer_photo(
            photo=moral_img,
            caption=moral_text,
            reply_markup=get_workshop_keyboard(WORKSHOP_URL),
        )
    else:
        await callback.message.answer(
            moral_text,
            reply_markup=get_workshop_keyboard(WORKSHOP_URL),
        )
