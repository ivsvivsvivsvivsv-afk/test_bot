from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb_answer_with_check(wisdom_prompt: str) -> InlineKeyboardMarkup:
    """
    Клавиатура:
    ✅ Правда | ❌ Ложь
    🔍 Иду проверять (Perplexity)
    """
    url = f"https://www.perplexity.ai/search?q={quote(wisdom_prompt)}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Правда", callback_data="answer_true"),
                InlineKeyboardButton(text="❌ Ложь", callback_data="answer_false"),
            ],
            [
                InlineKeyboardButton(text="🔍 Иду проверять", url=url),
            ],
        ]
    )


def kb_next_round() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Дальше", callback_data="next_round")]
        ]
    )
