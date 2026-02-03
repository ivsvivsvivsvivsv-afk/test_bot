from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import time

from database import create_user, get_user, update_user
from keyboards.inline import kb_start, kb_class, kb_already_played
from texts import MESSAGES, URLS
from utils.images import send_image_if_exists, delete_message_safe
from config import ADMIN_IDS

router = Router()


async def _delete_previous_image(bot, user_id: int, chat_id: int):
    """Delete previously sent image message if exists."""
    user = await get_user(user_id)
    if user and user.get("last_image_msg_id"):
        await delete_message_safe(bot, chat_id, user["last_image_msg_id"])
        await update_user(user_id, last_image_msg_id=None)


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await get_user(message.from_user.id)

    # Delete any previous image from past sessions
    await _delete_previous_image(message.bot, message.from_user.id, message.chat.id)

    if user and user.get("quest_completed"):
        # Send image and save its message_id
        img_msg_id = await send_image_if_exists(message, ['img_already_played', 'img_start_portal'])
        if img_msg_id:
            await update_user(message.from_user.id, last_image_msg_id=img_msg_id)
        
        await message.answer(MESSAGES["already_played"], reply_markup=kb_already_played())
        return

    await update_user(message.from_user.id, state="start")
    
    # Send image and save its message_id
    img_msg_id = await send_image_if_exists(message, ['img_start_portal'])
    if img_msg_id:
        await update_user(message.from_user.id, last_image_msg_id=img_msg_id)
    
    await message.answer(MESSAGES["start"], reply_markup=kb_start())


@router.callback_query(F.data == "open_generator")
async def open_generator(cb: CallbackQuery):
    await cb.message.answer(f"🎬 {URLS.get('generator_bot')}")
    await cb.answer()


@router.callback_query(F.data == "start_quest")
async def start_quest(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass

    # Reset user state for new quest
    await update_user(
        user_id,
        state="class",
        score=0,
        round_number=0,
        player_class=None,
        weapon=None,
        other_sphere=None,
        quest_started_at=int(time.time()),
        last_image_msg_id=None,
    )
    
    # Send new image and save its message_id
    img_msg_id = await send_image_if_exists(cb.message, ['img_class_choice'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    # Send text with keyboard
    await cb.message.answer(MESSAGES["class_choice"], reply_markup=kb_class())
    await cb.answer()


@router.callback_query(F.data == "signup_workshop_direct")
async def signup_workshop_direct(cb: CallbackQuery):
    """Direct workshop signup for users who already completed the quest."""
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await update_user(user_id, state="wait_phone")
    
    # Send workshop phone ask image
    img_msg_id = await send_image_if_exists(cb.message, ['img_workshop_ask_phone'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    await cb.message.answer(MESSAGES["ask_phone"])
    await cb.answer()


@router.message(Command("restart_mode"))
async def cmd_restart_mode(message: Message):
    """Admin command to reset user state for testing. Usage: /restart_mode hydra2026"""
    user_id = message.from_user.id
    
    # Check secret code OR admin status
    args = message.text.split()
    secret_code = args[1] if len(args) > 1 else ""
    
    # Allow if: correct secret code OR user is in ADMIN_IDS
    if secret_code != "hydra2026" and user_id not in ADMIN_IDS:
        # Silently ignore
        return
    
    # Delete previous image
    await _delete_previous_image(message.bot, user_id, message.chat.id)
    
    # Full reset of user state
    await update_user(
        user_id,
        state="start",
        quest_completed=0,
        score=0,
        round_number=0,
        player_class=None,
        weapon=None,
        other_sphere=None,
        current_statement=None,
        current_is_truth=0,
        current_wisdom_prompt=None,
        phone=None,
        email=None,
        workshop_registered=0,
        arena_registered=0,
        quest_started_at=None,
        last_image_msg_id=None,
    )
    
    await message.answer(
        "🔄 <b>РЕЖИМ ТЕСТИРОВАНИЯ</b>\n\n"
        "Твой прогресс полностью сброшен.\n"
        "Теперь можешь пройти квест заново.\n\n"
        "Нажми /start чтобы начать.",
        parse_mode="HTML"
    )
