from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database import create_user, get_user, update_user
from keyboards.inline import kb_start, kb_class
from texts import MESSAGES, URLS
from utils.images import send_image_if_exists, send_photo_with_caption

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
        user = await get_user(message.from_user.id)

    if user and user.get("quest_completed"):
        # Already played - try to send photo with caption
        text = MESSAGES["already_played"]
        keyboard = kb_start()
        
        photo_sent = await send_photo_with_caption(
            message, ['img_already_played', 'img_start_portal'], 
            caption=text, reply_markup=keyboard
        )
        
        if not photo_sent:
            await message.answer(text, reply_markup=keyboard)
        return

    await update_user(message.from_user.id, state="start")
    
    # Try to send photo with caption
    text = MESSAGES["start"]
    keyboard = kb_start()
    
    photo_sent = await send_photo_with_caption(
        message, ['img_start_portal'], caption=text, reply_markup=keyboard
    )
    
    if not photo_sent:
        await message.answer(text, reply_markup=keyboard)


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
    
    # Delete old message to avoid stale content
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    # Try to send photo with caption, fallback to text only
    text = MESSAGES["class_choice"]
    keyboard = kb_class()
    
    photo_sent = await send_photo_with_caption(
        cb.message, ['img_class_choice'], caption=text, reply_markup=keyboard
    )
    
    if not photo_sent:
        await cb.message.answer(text, reply_markup=keyboard)
    
    await cb.answer()
