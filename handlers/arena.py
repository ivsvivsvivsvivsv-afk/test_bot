from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from database import get_user, update_user
from texts import MESSAGES
from utils.validation import validate_phone, validate_email
from utils.notifications import notify_admin, build_lead_arena
from keyboards.inline import kb_go_to_quest
from utils.db_filters import DBStateFilter
from utils.images import send_image_if_exists, delete_message_safe

router = Router()


async def _delete_previous_image(bot, user_id: int, chat_id: int):
    """Delete previously sent image message if exists."""
    user = await get_user(user_id)
    if user and user.get("last_image_msg_id"):
        await delete_message_safe(bot, chat_id, user["last_image_msg_id"])
        await update_user(user_id, last_image_msg_id=None)


@router.callback_query(F.data == "arena_signup")
async def arena_signup(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await update_user(user_id, state="arena_wait_phone")
    
    # Send arena intro image
    img_msg_id = await send_image_if_exists(cb.message, ['img_arena_intro'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    await cb.message.answer(MESSAGES["arena_intro"])
    await cb.message.answer(MESSAGES["ask_phone"])
    await cb.answer()


@router.message(DBStateFilter("arena_wait_phone", "arena_wait_email"))
async def arena_flow(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    if user.get("state") == "arena_wait_phone":
        ok, phone = validate_phone(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_phone"])
            return
        
        # Delete previous image
        await _delete_previous_image(message.bot, user_id, chat_id)
        
        await update_user(user_id, phone=phone, state="arena_wait_email")
        
        # Send arena ask phone image
        img_msg_id = await send_image_if_exists(message, ['img_arena_ask_phone'])
        if img_msg_id:
            await update_user(user_id, last_image_msg_id=img_msg_id)
        
        await message.answer(MESSAGES["ask_email"])
        return

    if user.get("state") == "arena_wait_email":
        ok, email = validate_email(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_email"])
            return

        # Delete previous image
        await _delete_previous_image(message.bot, user_id, chat_id)

        await update_user(user_id, email=email, arena_registered=1, state="start", last_image_msg_id=None)

        fresh = await get_user(user_id)
        text = build_lead_arena(fresh, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"))
        await notify_admin(message.bot, text)

        # Send arena complete image
        img_msg_id = await send_image_if_exists(message, ['img_arena_complete'])
        if img_msg_id:
            await update_user(user_id, last_image_msg_id=img_msg_id)

        await message.answer(MESSAGES["arena_complete"], reply_markup=kb_go_to_quest())
        return
