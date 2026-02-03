from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from database import get_user, update_user
from keyboards.inline import (
    kb_weapon, kb_go_check, kb_answer, kb_next_round, kb_show_moral, kb_want_workshop
)
from texts import MESSAGES, ROUND_NAMES
from utils.statements import get_statement_for_round
from utils.notifications import notify_admin, build_prize_candidate
from utils.images import resolve_round_intro_image_key, send_image_if_exists, send_photo_with_caption
from utils.db_filters import DBStateFilter

router = Router()


@router.callback_query(F.data.in_({"class_boss", "class_freelancer"}))
async def class_selected(cb: CallbackQuery):
    player_class = "businessman" if cb.data == "class_boss" else "freelancer"
    await update_user(cb.from_user.id, player_class=player_class, state="weapon")
    
    # Delete old message (may be photo with caption)
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    # Try to send photo with caption for weapon choice
    photo_sent = await send_photo_with_caption(
        cb.message, ['img_weapon_choice'], 
        caption=MESSAGES["weapon_choice"], 
        reply_markup=kb_weapon()
    )
    
    if not photo_sent:
        await cb.message.answer(MESSAGES["weapon_choice"], reply_markup=kb_weapon())
    
    await cb.answer()


@router.callback_query(F.data.startswith("weapon_"))
async def weapon_selected(cb: CallbackQuery):
    weapon = cb.data.replace("weapon_", "").strip()

    if weapon == "other":
        await update_user(cb.from_user.id, weapon="other", state="weapon_other_ask")
        
        # Delete old message (may be photo with caption)
        try:
            await cb.message.delete()
        except Exception:
            pass
        
        # Try to send photo with caption for "other" prompt
        photo_sent = await send_photo_with_caption(
            cb.message, ['img_weapon_other_ask'],
            caption=MESSAGES["weapon_other_ask"],
            reply_markup=None
        )
        
        if not photo_sent:
            await cb.message.answer(MESSAGES["weapon_other_ask"])
        
        await cb.answer()
        return

    await update_user(cb.from_user.id, weapon=weapon)
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
    user_id = target.from_user.id if hasattr(target, "from_user") else target.message.from_user.id
    user = await get_user(user_id)
    weapon = (user.get("weapon") or "other").strip()

    data = get_statement_for_round(weapon, round_num)

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
    keyboard = kb_go_check()

    # Determine message target
    if hasattr(target, "message"):  # CallbackQuery
        msg_target = target.message
        # Delete old message to avoid stale content
        try:
            await target.message.delete()
        except Exception:
            pass
    else:  # Message
        msg_target = target

    # Try to send photo with caption, fallback to text only
    photo_sent = await send_photo_with_caption(
        msg_target, image_key, caption=text, reply_markup=keyboard
    )
    
    if not photo_sent:
        # No image found, send text message
        await msg_target.answer(text, reply_markup=keyboard)

    if hasattr(target, "answer"):
        try:
            await target.answer()
        except Exception:
            pass


@router.callback_query(F.data == "go_check")
async def go_check(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    rn = int(user.get("round_number") or 1)
    await update_user(cb.from_user.id, state=f"round_{rn}_answer")
    
    # Delete old message (may be photo with caption)
    try:
        await cb.message.delete()
    except Exception:
        pass
    
    await cb.message.answer(MESSAGES["answer_prompt"], reply_markup=kb_answer())
    await cb.answer()


@router.callback_query(F.data.in_({"answer_true", "answer_false"}))
async def answer(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    rn = int(user.get("round_number") or 1)

    player_says_true = cb.data == "answer_true"
    truth = bool(user.get("current_is_truth"))
    is_correct = (player_says_true == truth)

    score = int(user.get("score") or 0)
    if is_correct:
        score += 1

    await update_user(cb.from_user.id, score=score)

    head_key = f"round{rn}_cut" if is_correct else f"round{rn}_alive"
    head_message = MESSAGES["head_messages"].get(head_key, "")

    if is_correct:
        result_text = MESSAGES["result_correct"].format(score=score, head_message=head_message)
    else:
        continue_message = "Продолжаем." if rn < 3 else "Это был последний раунд."
        result_text = MESSAGES["result_wrong"].format(score=score, continue_message=continue_message)

    if rn < 3:
        await update_user(cb.from_user.id, state=f"round_{rn}_result")
        await cb.message.edit_text(result_text, reply_markup=kb_next_round(rn + 1))
        await cb.answer()
        return

    # раунд 3 → победа/частичная + show_moral
    await update_user(cb.from_user.id, state="results", quest_completed=1)

    # prize candidate notify (3/3)
    if score >= 3:
        user_for_admin = dict(user)
        user_for_admin["score"] = score
        await notify_admin(cb.message.bot, build_prize_candidate(user_for_admin))

    victory_block = MESSAGES["victory_full"] if score >= 3 else MESSAGES["victory_partial"].format(score=score)
    await cb.message.edit_text(result_text + "\n\n" + victory_block, reply_markup=kb_show_moral())
    await cb.answer()


@router.callback_query(F.data.startswith("next_round_"))
async def next_round(cb: CallbackQuery):
    next_r = int(cb.data.replace("next_round_", ""))
    await _send_round_intro(cb, round_num=next_r)


@router.callback_query(F.data == "show_moral")
async def show_moral(cb: CallbackQuery):
    # экран морали + кнопка "хочу на воркшоп"
    await update_user(cb.from_user.id, state="moral")
    await cb.message.edit_text(MESSAGES["moral"], reply_markup=kb_want_workshop())
    await cb.answer()


@router.callback_query(F.data == "want_workshop")
async def want_workshop(cb: CallbackQuery):
    # после морали → сбор контактов (phone/email) в contacts.py
    await update_user(cb.from_user.id, state="wait_phone")
    await cb.message.answer(MESSAGES["ask_phone"])
    await cb.answer()


