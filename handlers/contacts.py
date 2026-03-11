"""
Contact collection handler.

Provides FSM-based flow: phone (mandatory) → confirmation → save.
Telegram @username is captured automatically — no manual input needed.
Email is NOT collected (removed per business requirements).

Called from quest.py (after moral) or from arena.py (after hackathon qualification).
Uses asyncpg.Pool directly (no legacy Database wrapper).
"""

from __future__ import annotations

import logging

import asyncpg
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.inline import CB, get_start_keyboard, remove_keyboard, single_button
from utils.content_manager import ContentManager
from utils.media_ids import get_file_id
from utils.notifications import notify_new_contact
from utils.validation import validate_phone

logger = logging.getLogger(__name__)
router = Router(name="contacts")


# ── FSM states ──────────────────────────────────────────────


class ContactStates(StatesGroup):
    waiting_phone = State()
    confirming = State()


# ── Keyboards (local to this module) ────────────────────────


def _confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{CB.CONTACT}:confirm"))
    b.row(InlineKeyboardButton(text="✏️ Изменить телефон", callback_data=f"{CB.CONTACT}:edit_phone"))
    return b.as_markup()


def _success_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🎓 Узнать о курсе", callback_data=f"{CB.CONTACT}:to_course"))
    b.row(InlineKeyboardButton(text="🏠 В начало", callback_data=f"{CB.CONTACT}:to_start"))
    return b.as_markup()


def _start_contact_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📱 Оставить контакт", callback_data=f"{CB.CONTACT}:start"))
    b.row(InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"{CB.CONTACT}:skip_all"))
    return b.as_markup()


# ── Helpers ─────────────────────────────────────────────────


async def _safe_remove_kb(msg: Message) -> None:
    try:
        await msg.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest:
        pass


async def _save_contacts(
    pool: asyncpg.Pool,
    user_id: int,
    phone: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET
                phone = $2
            WHERE user_id = $1
            """,
            user_id, phone,
        )


# ── Public entry point (called from quest.py / arena.py) ────


async def start_contact_collection(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    user_id: int,
) -> None:
    from services.quest_service import get_user

    row = await get_user(pool, user_id)
    if row and row.get("phone"):
        await message.answer(
            "📱 У нас уже есть ваш телефон!\n\nХотите обновить его?",
            reply_markup=_start_contact_kb(),
        )
    else:
        intro_text = ContentManager.get_raw("contact_intro")
        img_final = get_file_id("img_final")
        if img_final:
            await message.answer_photo(
                photo=img_final,
                caption=intro_text,
                reply_markup=_start_contact_kb(),
            )
        else:
            await message.answer(intro_text, reply_markup=_start_contact_kb())


# ── Start contact flow ──────────────────────────────────────


@router.callback_query(F.data == f"{CB.CONTACT}:start")
async def cb_start_contact(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    tg_username = callback.from_user.username
    logger.info("User %s contact start (tg_username=%s)", user_id, tg_username)

    await _safe_remove_kb(callback.message)
    await callback.answer()

    await state.set_state(ContactStates.waiting_phone)
    await state.update_data(
        phone=None,
        tg_username=f"@{tg_username}" if tg_username else None,
    )

    await callback.message.answer(
        ContentManager.get_raw("contact_phone_request"),
    )


# ── Skip all contacts ───────────────────────────────────────


@router.callback_query(F.data == f"{CB.CONTACT}:skip_all")
async def cb_skip_all(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info("User %s skipped all contacts", callback.from_user.id)
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.clear()

    await callback.message.answer(
        ContentManager.get_raw("contact_skipped"),
        reply_markup=_success_kb(),
    )


# ── Edit phone (from confirmation screen) ───────────────────


@router.callback_query(F.data == f"{CB.CONTACT}:edit_phone")
async def cb_edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.set_state(ContactStates.waiting_phone)
    await callback.message.answer(
        ContentManager.get_raw("contact_phone_request"),
    )


# ── Confirm ─────────────────────────────────────────────────


@router.callback_query(F.data == f"{CB.CONTACT}:confirm")
async def cb_confirm_contacts(
    callback: CallbackQuery,
    state: FSMContext,
    pool: asyncpg.Pool,
    redis_conn,
) -> None:
    user_id = callback.from_user.id
    data = await state.get_data()
    phone = data.get("phone")
    tg_username = data.get("tg_username")

    if not phone:
        await callback.answer("Телефон не указан!", show_alert=True)
        return

    logger.info(
        "User %s confirmed contacts: phone=%s tg_username=%s",
        user_id, phone, tg_username,
    )

    await _safe_remove_kb(callback.message)
    await callback.answer("✅ Контакты сохранены!")

    await _save_contacts(pool, user_id, phone)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET workshop_registered = TRUE WHERE user_id = $1",
            user_id,
        )

    from services.quest_service import log_event
    await log_event(pool, user_id, "contact_phone", {"phone": phone})
    await log_event(pool, user_id, "workshop_registered", {})

    await notify_new_contact(
        bot=callback.bot,
        user_id=user_id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
        phone=phone,
    )

    await state.clear()

    await callback.message.answer(
        ContentManager.get_raw("contact_success"),
        reply_markup=_success_kb(),
    )

    try:
        from handlers.upsell import show_upsell_if_available
        await show_upsell_if_available(
            bot=callback.bot,
            user_id=user_id,
            chat_id=callback.message.chat.id,
            pool=pool,
            redis_conn=redis_conn,
        )
    except Exception:
        logger.debug("upsell not available", exc_info=True)


# ── Navigation after success ────────────────────────────────


@router.callback_query(F.data == f"{CB.CONTACT}:to_course")
async def cb_to_course(callback: CallbackQuery) -> None:
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await callback.message.answer(ContentManager.get_raw("about_course"))


@router.callback_query(F.data == f"{CB.CONTACT}:to_start")
async def cb_to_start(callback: CallbackQuery, state: FSMContext) -> None:
    await _safe_remove_kb(callback.message)
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        ContentManager.get("welcome"),
        reply_markup=get_start_keyboard(),
    )


# ── Text input handler: phone (FSM-guarded) ─────────────────


@router.message(ContactStates.waiting_phone, F.text, ~F.text.startswith("/"))
async def process_phone_input(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    phone_input = (message.text or "").strip()

    result = validate_phone(phone_input)
    if not result.is_valid:
        await message.answer(
            f"❌ {result.error}\n\n"
            f"{ContentManager.get_raw('contact_phone_format_hint')}",
        )
        return

    logger.info("User %s phone validated", user_id)
    await state.update_data(phone=result.normalized_value)

    await _show_confirmation(message, state)


# ── Confirmation screen ─────────────────────────────────────


async def _show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    phone = data.get("phone")
    tg_username = data.get("tg_username")

    phone_display = f"<code>{phone}</code>" if phone else "не указан"
    username_display = f"<code>{tg_username}</code>" if tg_username else "не установлен"

    await state.set_state(ContactStates.confirming)
    await message.answer(
        f"📋 <b>Проверьте ваши данные:</b>\n\n"
        f"📞 Телефон: {phone_display}\n"
        f"🔗 Telegram: {username_display}\n\n"
        "Всё верно?",
        reply_markup=_confirm_kb(),
    )
