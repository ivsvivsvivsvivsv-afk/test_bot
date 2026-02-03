from aiogram import Router
from aiogram.types import Message
import time

from database import get_user, update_user
from utils.validation import validate_phone, validate_email
from utils.notifications import notify_admin, build_lead_workshop
from utils.db_filters import DBStateFilter
from texts import MESSAGES, WEAPON_LABELS
from keyboards.inline import kb_open_generator
from utils.images import send_image_if_exists, delete_message_safe

router = Router()


async def _delete_previous_image(bot, user_id: int, chat_id: int):
    """Delete previously sent image message if exists."""
    user = await get_user(user_id)
    if user and user.get("last_image_msg_id"):
        await delete_message_safe(bot, chat_id, user["last_image_msg_id"])
        await update_user(user_id, last_image_msg_id=None)


@router.message(DBStateFilter("wait_phone", "wait_email"))
async def contacts_flow(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    state = user.get("state")

    if state == "wait_phone":
        ok, phone = validate_phone(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_phone"])
            return

        # Delete previous image
        await _delete_previous_image(message.bot, user_id, chat_id)

        await update_user(user_id, phone=phone, state="wait_email")
        
        # Send email ask image
        img_msg_id = await send_image_if_exists(message, ['img_workshop_ask_email'])
        if img_msg_id:
            await update_user(user_id, last_image_msg_id=img_msg_id)
        
        await message.answer(MESSAGES["ask_email"])
        return

    if state == "wait_email":
        ok, email = validate_email(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_email"])
            return

        # Delete previous image
        await _delete_previous_image(message.bot, user_id, chat_id)

        # workshop registered
        await update_user(user_id, email=email, workshop_registered=1, state="completed", last_image_msg_id=None)

        # notify admin with duration/actions
        fresh = await get_user(user_id)

        started = fresh.get("quest_started_at") or int(time.time())
        duration_sec = max(0, int(time.time()) - int(started))
        duration = f"{duration_sec}s"

        actions = f"{fresh.get('player_class')}>{fresh.get('weapon')}"
        text = build_lead_workshop(fresh, actions=actions, duration=duration)
        await notify_admin(message.bot, text)

        # Send final image
        img_msg_id = await send_image_if_exists(message, ['img_workshop_final'])
        if img_msg_id:
            await update_user(user_id, last_image_msg_id=img_msg_id)

        await message.answer(MESSAGES["final"], reply_markup=kb_open_generator())
        return
