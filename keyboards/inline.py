from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# START / CLASS
# =========================

def kb_start() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Начать испытание", callback_data="start_quest")
    return kb.as_markup()


def kb_class() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 Маркетинг", callback_data="class_marketing")
    kb.button(text="🎨 Дизайн", callback_data="class_design")
    kb.button(text="✍️ Копирайтинг", callback_data="class_copywriting")
    kb.adjust(1)
    return kb.as_markup()


# =========================
# QUEST ANSWERS
# =========================

def kb_answer() -> InlineKeyboardMarkup:
    """
    Базовые кнопки ответа: Правда / Ложь
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Правда", callback_data="answer_true")
    kb.button(text="❌ Ложь", callback_data="answer_false")
    kb.adjust(2)
    return kb.as_markup()


def kb_go_check() -> InlineKeyboardMarkup:
    """
    Кнопка 'Иду проверять'
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Иду проверять", callback_data="go_check")
    return kb.as_markup()


# =========================
# NEXT ROUND
# =========================

def kb_next_round_num(round_num: int) -> InlineKeyboardMarkup:
    """
    Кнопка следующего раунда (основная реализация)
    """
    kb = InlineKeyboardBuilder()
    kb.button(
        text="➡️ Следующее испытание",
        callback_data=f"next_round:{round_num}"
    )
    return kb.as_markup()


# =========================
# 🔥 ALIASES (ВАЖНО)
# =========================
# Эти функции НУЖНЫ, потому что handlers их импортируют
# НЕ УДАЛЯТЬ

def kb_answer_with_check(wisdom_prompt: str = "") -> InlineKeyboardMarkup:
    """
    Алиас для старых handler'ов.
    wisdom_prompt не используется — логика в тексте.
    """
    return kb_answer()


def kb_next_round() -> InlineKeyboardMarkup:
    """
    Алиас без аргументов (по умолчанию следующий раунд = 2)
    """
    return kb_next_round_num(2)
