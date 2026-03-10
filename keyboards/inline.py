"""
Inline keyboards for the Hydra Singularity bot.

All callback_data values follow the pattern ``prefix:action[:param]``.
Buttons are deactivated after click via ``edit_reply_markup(reply_markup=None)``.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ── Callback prefixes ───────────────────────────────────────


class CB:
    START = "start"
    QUEST = "quest"
    ARENA = "arena"
    CONTACT = "contact"
    UPSELL = "upsell"
    MINIQUEST = "miniquest"
    ADMIN = "admin"


# Keep legacy alias for imports that use the old name
CallbackPrefixes = CB


# ── Utility ─────────────────────────────────────────────────


def remove_keyboard() -> None:
    """Return None to clear reply_markup when editing a message."""
    return None


def single_button(text: str, callback_data: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=text, callback_data=callback_data))
    return b.as_markup()


def url_button(text: str, url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=text, url=url))
    return b.as_markup()


# ── Start ───────────────────────────────────────────────────


def get_start_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🎮 Начать Квест", callback_data=f"{CB.START}:begin_quest"))
    b.row(InlineKeyboardButton(text="🎬 Генератор видео", callback_data=f"{CB.START}:generator"))
    b.row(InlineKeyboardButton(text="⚔️ Арена", callback_data=f"{CB.START}:arena"))
    return b.as_markup()


def get_continue_keyboard() -> InlineKeyboardMarkup:
    return single_button("✅ Понятно, продолжить", f"{CB.START}:continue")


def get_welcome_back_keyboard() -> InlineKeyboardMarkup:
    """Shown to users who already completed the quest."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📝 Записаться на воркшоп", callback_data=f"{CB.QUEST}:workshop"))
    b.row(InlineKeyboardButton(text="📚 О курсе", callback_data=f"{CB.START}:about_course"))
    return b.as_markup()


def get_resume_keyboard() -> InlineKeyboardMarkup:
    """Shown to users whose quest is in progress (interrupted)."""
    return single_button("▶️ Продолжить квест", f"{CB.QUEST}:resume")


# ── Quest: class selection ──────────────────────────────────


HERO_CLASSES = {
    "businessman": {"name": "💼 Бизнесмен", "emoji": "💼", "desc": "Строит империю с помощью ИИ"},
    "creator":     {"name": "🎨 Творец",     "emoji": "🎨", "desc": "Создает контент с помощью ИИ"},
    "analyst":     {"name": "📊 Аналитик",   "emoji": "📊", "desc": "Анализирует данные с помощью ИИ"},
    "manager":     {"name": "📋 Менеджер",   "emoji": "📋", "desc": "Управляет проектами с ИИ"},
}


def get_class_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cid, info in HERO_CLASSES.items():
        b.row(InlineKeyboardButton(
            text=info["name"],
            callback_data=f"{CB.QUEST}:class:{cid}",
        ))
    return b.as_markup()


# ── Quest: weapon selection ─────────────────────────────────


WEAPONS = {
    "marketing":   {"name": "📢 Мегафон Маркетолога",   "emoji": "📢", "desc": "Продвижение и реклама"},
    "analytics":   {"name": "👁️ Глаз Аналитика",       "emoji": "👁️", "desc": "Данные и аналитика"},
    "copywriting": {"name": "✍️ Перо Копирайтера",      "emoji": "✍️", "desc": "Тексты и контент"},
    "design":      {"name": "🖊️ Планшет Дизайнера",     "emoji": "🖊️", "desc": "Визуальный контент"},
    "management":  {"name": "🤝 Рука Координатора",     "emoji": "🤝", "desc": "Управление и процессы"},
    "video":       {"name": "🎬 Камера Видеомейкера",   "emoji": "🎬", "desc": "Видеоконтент"},
}


def get_weapon_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for wid, info in WEAPONS.items():
        b.row(InlineKeyboardButton(
            text=info["name"],
            callback_data=f"{CB.QUEST}:weapon:{wid}",
        ))
    return b.as_markup()


# ── Quest: round answer ────────────────────────────────────


def get_answer_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Правда", callback_data=f"{CB.QUEST}:answer:true"),
        InlineKeyboardButton(text="❌ Ложь",   callback_data=f"{CB.QUEST}:answer:false"),
    )
    return b.as_markup()


def get_next_round_keyboard(is_last: bool = False) -> InlineKeyboardMarkup:
    if is_last:
        return single_button("🏆 Узнать результат", f"{CB.QUEST}:show_result")
    return single_button("➡️ Следующий раунд", f"{CB.QUEST}:next_round")


# ── Quest: finish (NO restart button!) ─────────────────────


def get_finish_keyboard() -> InlineKeyboardMarkup:
    """Only the gift button — user CANNOT replay the quest."""
    return single_button("🎁 Получить подарок", f"{CB.QUEST}:get_prize")


# ── Quest: moral → workshop ────────────────────────────────


def get_moral_keyboard() -> InlineKeyboardMarkup:
    return single_button("🎁 Получить подарок", f"{CB.QUEST}:get_prize")


def get_workshop_keyboard(url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🚀 Хочу на воркшоп!", url=url))
    return b.as_markup()


# ── Arena (hackathon) ────────────────────────────────────────


def get_arena_intro_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🏆 Хочу участвовать!", callback_data=f"{CB.ARENA}:participate"))
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{CB.ARENA}:back"))
    return b.as_markup()


def get_arena_q1_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    from utils.content_manager import ContentManager
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q1_opt_beginner"), callback_data=f"{CB.ARENA}:q1:beginner"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q1_opt_intermediate"), callback_data=f"{CB.ARENA}:q1:intermediate"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q1_opt_advanced"), callback_data=f"{CB.ARENA}:q1:advanced"))
    return b.as_markup()


def get_arena_q2_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    from utils.content_manager import ContentManager
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q2_opt_chat"), callback_data=f"{CB.ARENA}:q2:chat"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q2_opt_image"), callback_data=f"{CB.ARENA}:q2:image"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q2_opt_dev"), callback_data=f"{CB.ARENA}:q2:dev"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q2_opt_all"), callback_data=f"{CB.ARENA}:q2:all"))
    return b.as_markup()


def get_arena_q3_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    from utils.content_manager import ContentManager
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q3_opt_bot"), callback_data=f"{CB.ARENA}:q3:bot"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q3_opt_analytics"), callback_data=f"{CB.ARENA}:q3:analytics"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q3_opt_content"), callback_data=f"{CB.ARENA}:q3:content"))
    b.row(InlineKeyboardButton(text=ContentManager.get_raw("arena_q3_opt_custom"), callback_data=f"{CB.ARENA}:q3:custom"))
    return b.as_markup()


def get_arena_contacts_keyboard() -> InlineKeyboardMarkup:
    return single_button("📱 Оставить контакты", f"{CB.ARENA}:contacts")


def get_arena_quest_offer_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🎮 Пройти квест", callback_data=f"{CB.ARENA}:to_quest"))
    b.row(InlineKeyboardButton(text="❌ Нет, спасибо", callback_data=f"{CB.ARENA}:decline_quest"))
    return b.as_markup()


# ── Contact ─────────────────────────────────────────────────


def get_contact_start_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📱 Оставить контакт", callback_data=f"{CB.CONTACT}:start"))
    b.row(InlineKeyboardButton(text="❌ Позже", callback_data=f"{CB.CONTACT}:skip"))
    return b.as_markup()


def get_miniquest_answer_keyboard(day: int) -> InlineKeyboardMarkup:
    """ПРАВДА / ЛОЖЬ for miniquest."""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ ПРАВДА",
            callback_data=f"{CB.MINIQUEST}:answer:{day}:true",
        ),
        InlineKeyboardButton(
            text="❌ ЛОЖЬ",
            callback_data=f"{CB.MINIQUEST}:answer:{day}:false",
        ),
    )
    return b.as_markup()


def get_miniquest_cta_keyboard(day: int) -> InlineKeyboardMarkup:
    """📝 Записаться | ⏭ Позже after miniquest answer."""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="📝 Записаться",
            callback_data=f"{CB.MINIQUEST}:register:{day}",
        ),
        InlineKeyboardButton(
            text="⏭ Позже",
            callback_data=f"{CB.MINIQUEST}:later:{day}",
        ),
    )
    return b.as_markup()


def get_contact_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation screen: approve or edit phone."""
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{CB.CONTACT}:confirm"))
    b.row(InlineKeyboardButton(text="✏️ Изменить телефон", callback_data=f"{CB.CONTACT}:edit_phone"))
    return b.as_markup()


# ── Admin ───────────────────────────────────────────────────


def get_admin_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📊 Статистика", callback_data=f"{CB.ADMIN}:stats"))
    b.row(InlineKeyboardButton(text="👥 Пользователи", callback_data=f"{CB.ADMIN}:users"))
    b.row(InlineKeyboardButton(text="📤 Экспорт контактов", callback_data=f"{CB.ADMIN}:export"))
    return b.as_markup()


# ── Generic helpers ─────────────────────────────────────────


def parse_callback_data(callback_data: str) -> tuple[str, list[str]]:
    parts = callback_data.split(":")
    return parts[0], parts[1:]
