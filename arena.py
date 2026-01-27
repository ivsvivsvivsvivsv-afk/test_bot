from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from database import get_user, update_user
from texts import MESSAGES
from utils.validation import validate_phone, validate_email
from utils.notifications import notify_admin, build_lead_arena

router = Router()


@router.callback_query(F.data == "arena_signup")
async def arena_signup(cb: CallbackQuery):
    await update_user(cb.from_user.id, state="arena_wait_phone")
    await cb.message.edit_text(MESSAGES["arena_intro"])
    await cb.message.answer(MESSAGES["ask_phone"])
    await cb.answer()


@router.message()
async def arena_flow(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return

    if user.get("state") == "arena_wait_phone":
        ok, phone = validate_phone(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_phone"])
            return
        await update_user(message.from_user.id, phone=phone, state="arena_wait_email")
        await message.answer(MESSAGES["ask_email"])
        return

    if user.get("state") == "arena_wait_email":
        ok, email = validate_email(message.text or "")
        if not ok:
            await message.answer(MESSAGES["invalid_email"])
            return

        await update_user(message.from_user.id, email=email, arena_registered=1, state="start")

        fresh = await get_user(message.from_user.id)
        text = build_lead_arena(fresh, timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"))
        await notify_admin(message.bot, text)

        await message.answer(MESSAGES["arena_complete"])
        return
