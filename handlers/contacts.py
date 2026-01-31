from aiogram import Router
from aiogram.types import Message
import time

from database import get_user, update_user
from utils.validation import validate_phone, validate_email
from utils.notifications import notify_admin, build_lead_workshop
from utils.db_filters import DBStateFilter
from texts import MESSAGES, WEAPON_LABELS
from keyboards.inline import kb_open_generator

router = Router()


@router.message(DBStateFilter("wait_phone", "wait_email"))
async def contacts_flow(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return

    state = user.get("state")

    if state == "wait_phone":
        ok, phone = validate_phone(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_phone"])
            return

        await update_user(message.from_user.id, phone=phone, state="wait_email")
        await message.answer(MESSAGES["ask_email"])
        return

    if state == "wait_email":
        ok, email = validate_email(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_email"])
            return

        # workshop registered
        await update_user(message.from_user.id, email=email, workshop_registered=1, state="completed")

        # notify admin with duration/actions
        fresh = await get_user(message.from_user.id)

        started = fresh.get("quest_started_at") or int(time.time())
        duration_sec = max(0, int(time.time()) - int(started))
        duration = f"{duration_sec}s"

        actions = f"{fresh.get('player_class')}>{fresh.get('weapon')}"
        text = build_lead_workshop(fresh, actions=actions, duration=duration)
        await notify_admin(message.bot, text)

        await message.answer(MESSAGES["final"], reply_markup=kb_open_generator())
        return
