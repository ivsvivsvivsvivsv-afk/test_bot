from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from database import get_user, update_user
from keyboards.inline import (
    kb_weapon, kb_go_check, kb_answer, kb_next_round, kb_show_moral, kb_want_workshop
)
from texts import MESSAGES, ROUND_NAMES
from utils.statements import get_statement_for_round
from utils.notifications import notify_admin, build_prize_candidate
from utils.images import resolve_round_intro_image_key, send_image_if_exists, delete_message_safe
from utils.db_filters import DBStateFilter

router = Router()


async def _delete_previous_image(bot, user_id: int, chat_id: int):
    """Delete previously sent image message if exists."""
    user = await get_user(user_id)
    if user and user.get("last_image_msg_id"):
        await delete_message_safe(bot, chat_id, user["last_image_msg_id"])
        await update_user(user_id, last_image_msg_id=None)


@router.callback_query(F.data.in_({"class_boss", "class_freelancer"}))
async def class_selected(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    player_class = "businessman" if cb.data == "class_boss" else "freelancer"
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await update_user(user_id, player_class=player_class, state="weapon")
    
    # Send new image and save its message_id
    img_msg_id = await send_image_if_exists(cb.message, ['img_weapon_choice'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    # Send text with keyboard
    await cb.message.answer(MESSAGES["weapon_choice"], reply_markup=kb_weapon())
    await cb.answer()


@router.callback_query(F.data.startswith("weapon_"))
async def weapon_selected(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    weapon = cb.data.replace("weapon_", "").strip()

    if weapon == "other":
        # Delete previous image
        await _delete_previous_image(cb.bot, user_id, chat_id)
        
        # Delete the text message with button
        try:
            await cb.message.delete()
        except Exception:
            pass
        
        await update_user(user_id, weapon="other", state="weapon_other_ask")
        
        # Send new image and save its message_id
        img_msg_id = await send_image_if_exists(cb.message, ['img_weapon_other_ask'])
        if img_msg_id:
            await update_user(user_id, last_image_msg_id=img_msg_id)
        
        await cb.message.answer(MESSAGES["weapon_other_ask"])
        await cb.answer()
        return

    await update_user(user_id, weapon=weapon)
    await _send_round_intro(cb, round_num=1)


@router.message(DBStateFilter("weapon_other_ask"))
async def weapon_other_text(message: Message):
    user = await get_user(message.from_user.id)
    if not user or user.get("state") != "weapon_other_ask":
        return

    other = (message.text or "").strip()
    await update_user(message.from_user.id, weapon="other", other_sphere=other)
    await _send_round_intro(message, round_num=1)


async def _send_round_intro(target, round_num: int):
    """Send round intro with image and text."""
    # Determine user_id, chat_id, bot
    if hasattr(target, "message"):  # CallbackQuery
        user_id = target.from_user.id
        chat_id = target.message.chat.id
        bot = target.bot
        msg_target = target.message
        is_callback = True
    else:  # Message
        user_id = target.from_user.id
        chat_id = target.chat.id
        bot = target.bot
        msg_target = target
        is_callback = False

    user = await get_user(user_id)
    weapon = (user.get("weapon") or "other").strip()

    data = get_statement_for_round(weapon, round_num)

    # Delete previous image
    await _delete_previous_image(bot, user_id, chat_id)
    
    # Delete the text message with button (if callback)
    if is_callback:
        try:
            await target.message.delete()
        except Exception:
            pass

    await update_user(
        user_id,
        state=f"round_{round_num}_intro",
        round_number=round_num,
        current_statement=data["statement"],
        current_is_truth=int(data["is_truth"]),
        current_wisdom_prompt=data["wisdom_prompt"],
    )

    round_name = ROUND_NAMES.get(str(round_num), str(round_num))
    text = MESSAGES["round_intro"].format(
        round_name=round_name,
        statement=data["statement"],
        wisdom_prompt=data["wisdom_prompt"],
    )

    # Resolve image key (weapon first, then round_num!)
    image_key = resolve_round_intro_image_key(weapon, round_num)
    
    # Send new image and save its message_id
    img_msg_id = await send_image_if_exists(msg_target, image_key)
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    # Send text with keyboard
    await msg_target.answer(text, reply_markup=kb_go_check())
    
    if is_callback:
        try:
            await target.answer()
        except Exception:
            pass


@router.callback_query(F.data == "go_check")
async def go_check(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    user = await get_user(user_id)
    rn = int(user.get("round_number") or 1)
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await update_user(user_id, state=f"round_{rn}_answer")
    
    # Send new image (answer prompt) and save its message_id
    img_msg_id = await send_image_if_exists(cb.message, ['img_answer_prompt'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    await cb.message.answer(MESSAGES["answer_prompt"], reply_markup=kb_answer())
    await cb.answer()


@router.callback_query(F.data.in_({"answer_true", "answer_false"}))
async def answer(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    user = await get_user(user_id)
    rn = int(user.get("round_number") or 1)

    player_says_true = cb.data == "answer_true"
    truth = bool(user.get("current_is_truth"))
    is_correct = (player_says_true == truth)

    score = int(user.get("score") or 0)
    if is_correct:
        score += 1

    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass

    await update_user(user_id, score=score)

    head_key = f"round{rn}_cut" if is_correct else f"round{rn}_alive"
    head_message = MESSAGES["head_messages"].get(head_key, "")

    if is_correct:
        result_text = MESSAGES["result_correct"].format(score=score, head_message=head_message)
        img_key = 'img_result_correct'
    else:
        continue_message = "Продолжаем." if rn < 3 else "Это был последний раунд."
        result_text = MESSAGES["result_wrong"].format(score=score, continue_message=continue_message)
        img_key = 'img_result_wrong'

    # Send result image
    img_msg_id = await send_image_if_exists(cb.message, [img_key])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)

    if rn < 3:
        await update_user(user_id, state=f"round_{rn}_result")
        await cb.message.answer(result_text, reply_markup=kb_next_round(rn + 1))
        await cb.answer()
        return

    # раунд 3 → победа/частичная + show_moral
    await update_user(user_id, state="results", quest_completed=1)

    # prize candidate notify (3/3)
    if score >= 3:
        user_for_admin = dict(user)
        user_for_admin["score"] = score
        await notify_admin(cb.message.bot, build_prize_candidate(user_for_admin))

    victory_block = MESSAGES["victory_full"] if score >= 3 else MESSAGES["victory_partial"].format(score=score)
    await cb.message.answer(result_text + "\n\n" + victory_block, reply_markup=kb_show_moral())
    await cb.answer()


@router.callback_query(F.data.startswith("next_round_"))
async def next_round(cb: CallbackQuery):
    next_r = int(cb.data.replace("next_round_", ""))
    await _send_round_intro(cb, round_num=next_r)


@router.callback_query(F.data == "show_moral")
async def show_moral(cb: CallbackQuery):
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    
    # Delete previous image
    await _delete_previous_image(cb.bot, user_id, chat_id)
    
    # Delete the text message with button
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await update_user(user_id, state="moral")
    
    # Send moral image
    img_msg_id = await send_image_if_exists(cb.message, ['img_moral'])
    if img_msg_id:
        await update_user(user_id, last_image_msg_id=img_msg_id)
    
    await cb.message.answer(MESSAGES["moral"], reply_markup=kb_want_workshop())
    await cb.answer()


@router.callback_query(F.data == "want_workshop")
async def want_workshop(cb: CallbackQuery):
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
