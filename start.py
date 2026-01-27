from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database import create_user, get_user, update_user
from keyboards.inline import kb_start, kb_class
from texts import MESSAGES, URLS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await get_user(message.from_user.id)

    if user and user.get("quest_completed"):
        await message.answer(MESSAGES["already_played"], reply_markup=kb_start())
        return

    await update_user(message.from_user.id, state="start")
    await message.answer(MESSAGES["start"], reply_markup=kb_start())


@router.callback_query(F.data == "open_generator")
async def open_generator(cb: CallbackQuery):
    await cb.message.answer(f"🎬 {URLS.get('generator_bot')}")
    await cb.answer()


@router.callback_query(F.data == "start_quest")
async def start_quest(cb: CallbackQuery):
    # стартуем таймер воронки
    import time
    await update_user(
        cb.from_user.id,
        state="class",
        score=0,
        round_number=0,
        player_class=None,
        weapon=None,
        other_sphere=None,
        quest_started_at=int(time.time()),
    )
    await cb.message.edit_text(MESSAGES["class_choice"], reply_markup=kb_class())
    await cb.answer()
