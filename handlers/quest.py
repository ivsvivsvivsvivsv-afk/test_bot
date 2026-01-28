from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from keyboards.inline import kb_answer_with_check, kb_next_round

router = Router()

# =========================
# ДАННЫЕ РАУНДА (пример)
# =========================
ROUND_DATA = {
    "text": (
        "🐉 <b>ПЕРВОЕ ИСПЫТАНИЕ ГИДРЫ</b>\n\n"
        "📜 <b>УТВЕРЖДЕНИЕ:</b>\n"
        "Email-маркетинг имеет средний ROI около 36:1 — "
        "на каждый вложенный доллар возвращается $36.\n\n"
        "Это правда или ложь?\n\n"
        "🔮 <b>KSON даёт тебе ПРОМТ МУДРОСТИ:</b>\n"
        "Какой реальный ROI email-маркетинга? "
        "Найди данные из исследований Litmus или DMA."
    ),
    "wisdom_prompt": "Real ROI of email marketing Litmus DMA",
    "correct_answer": "true",
}

# =========================
# СТАРТ РАУНДА
# =========================
@router.message(F.text == "/start")
async def start_quest(message: Message):
    await message.answer(
        ROUND_DATA["text"],
        reply_markup=kb_answer_with_check(ROUND_DATA["wisdom_prompt"]),
    )

# =========================
# ОБРАБОТКА ОТВЕТОВ
# =========================
@router.callback_query(F.data.in_(["answer_true", "answer_false"]))
async def handle_answer(callback: CallbackQuery):
    user_answer = "true" if callback.data == "answer_true" else "false"

    if user_answer == ROUND_DATA["correct_answer"]:
        text = (
            "🔥 <b>Верно.</b>\n\n"
            "Email-маркетинг действительно показывает ROI ~36:1 "
            "по данным Litmus и DMA.\n\n"
            "Гидра отступает… пока."
        )
    else:
        text = (
            "💀 <b>Неверно.</b>\n\n"
            "Исследования Litmus/DMA показывают ROI около 36:1.\n"
            "Иногда знание — это тоже оружие."
        )

    await callback.message.edit_text(
        text,
        reply_markup=kb_next_round(),
    )
    await callback.answer()

# =========================
# СЛЕДУЮЩИЙ РАУНД (заглушка)
# =========================
@router.callback_query(F.data == "next_round")
async def next_round(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚔️ Следующее испытание уже готовится…",
    )
    await callback.answer()

