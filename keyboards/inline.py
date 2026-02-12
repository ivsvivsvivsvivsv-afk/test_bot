"""
Inline клавиатуры для бота НЕЙРО-ЮНИТ.

Особенности:
- Кнопки деактивируются после нажатия (удаляем reply_markup)
- Используем callback_data с префиксами для маршрутизации
- Поддержка одноразовых и многоразовых кнопок
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CALLBACK DATA PREFIXES
# =============================================================================
# Используем префиксы для идентификации типа действия

class CallbackPrefixes:
    """Префиксы для callback_data."""
    START = "start"
    QUEST = "quest"
    ARENA = "arena"
    CONTACT = "contact"
    ADMIN = "admin"


# =============================================================================
# СТАРТОВЫЕ КЛАВИАТУРЫ
# =============================================================================

def get_start_keyboard() -> InlineKeyboardMarkup:
    """
    Главная стартовая клавиатура.
    Показывается после приветствия.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚀 Начать квест",
            callback_data=f"{CallbackPrefixes.START}:begin_quest"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📚 Узнать больше о курсе",
            callback_data=f"{CallbackPrefixes.START}:about_course"
        )
    )
    return builder.as_markup()


def get_continue_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для продолжения после вводной информации."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Понятно, продолжить",
            callback_data=f"{CallbackPrefixes.START}:continue"
        )
    )
    return builder.as_markup()


# =============================================================================
# КВЕСТ КЛАВИАТУРЫ
# =============================================================================

def get_quest_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура начала квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎮 Погнали!",
            callback_data=f"{CallbackPrefixes.QUEST}:start"
        )
    )
    return builder.as_markup()


def get_quest_choice_keyboard(question_id: int, options: list[dict]) -> InlineKeyboardMarkup:
    """
    Клавиатура с вариантами ответа для квеста.
    
    Args:
        question_id: ID текущего вопроса
        options: Список вариантов [{text: str, value: str}, ...]
    """
    builder = InlineKeyboardBuilder()
    
    for opt in options:
        builder.row(
            InlineKeyboardButton(
                text=opt["text"],
                callback_data=f"{CallbackPrefixes.QUEST}:answer:{question_id}:{opt['value']}"
            )
        )
    
    return builder.as_markup()


def get_quest_continue_keyboard(next_step: str) -> InlineKeyboardMarkup:
    """Клавиатура для перехода к следующему шагу квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➡️ Далее",
            callback_data=f"{CallbackPrefixes.QUEST}:next:{next_step}"
        )
    )
    return builder.as_markup()


def get_quest_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после показа результатов квеста."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏆 Посмотреть мой результат",
            callback_data=f"{CallbackPrefixes.QUEST}:show_result"
        )
    )
    return builder.as_markup()


def get_quest_finish_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура завершения квеста - переход к сбору контактов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎁 Получить подарок",
            callback_data=f"{CallbackPrefixes.QUEST}:get_prize"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Пройти еще раз",
            callback_data=f"{CallbackPrefixes.QUEST}:restart"
        )
    )
    return builder.as_markup()


# =============================================================================
# АРЕНА КЛАВИАТУРЫ
# =============================================================================

def get_arena_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура начала арены."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⚔️ Войти на Арену",
            callback_data=f"{CallbackPrefixes.ARENA}:enter"
        )
    )
    return builder.as_markup()


def get_arena_specialization_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора специализации на арене."""
    specializations = [
        ("📊 Маркетинг", "marketing"),
        ("📈 Аналитика", "analytics"),
        ("✍️ Копирайтинг", "copywriting"),
        ("🎨 Дизайн", "design"),
        ("📋 Менеджмент", "management"),
        ("🎬 Видео", "video"),
        ("💼 Универсал", "universal"),
    ]
    
    builder = InlineKeyboardBuilder()
    
    for text, value in specializations:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{CallbackPrefixes.ARENA}:spec:{value}"
            )
        )
    
    return builder.as_markup()


def get_arena_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для задания арены."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Задание выполнено",
            callback_data=f"{CallbackPrefixes.ARENA}:complete:{task_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить",
            callback_data=f"{CallbackPrefixes.ARENA}:skip:{task_id}"
        )
    )
    return builder.as_markup()


def get_arena_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после результатов арены."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎁 Забрать приз",
            callback_data=f"{CallbackPrefixes.ARENA}:claim_prize"
        )
    )
    return builder.as_markup()


# =============================================================================
# КОНТАКТЫ КЛАВИАТУРЫ
# =============================================================================

def get_contact_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура начала сбора контактов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📱 Оставить контакт",
            callback_data=f"{CallbackPrefixes.CONTACT}:start"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Позже",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip"
        )
    )
    return builder.as_markup()


def get_contact_phone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода телефона (подсказка о формате)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить телефон",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip_phone"
        )
    )
    return builder.as_markup()


def get_contact_email_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода email."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить email",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip_email"
        )
    )
    return builder.as_markup()


def get_contact_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения контактных данных."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Всё верно",
            callback_data=f"{CallbackPrefixes.CONTACT}:confirm"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить телефон",
            callback_data=f"{CallbackPrefixes.CONTACT}:edit_phone"
        ),
        InlineKeyboardButton(
            text="✏️ Изменить email",
            callback_data=f"{CallbackPrefixes.CONTACT}:edit_email"
        )
    )
    return builder.as_markup()


def get_contact_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного сохранения контактов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎓 Узнать о курсе",
            callback_data=f"{CallbackPrefixes.CONTACT}:to_course"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data=f"{CallbackPrefixes.CONTACT}:to_menu"
        )
    )
    return builder.as_markup()


# =============================================================================
# АДМИН КЛАВИАТУРЫ
# =============================================================================

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data=f"{CallbackPrefixes.ADMIN}:stats"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Список пользователей",
            callback_data=f"{CallbackPrefixes.ADMIN}:users"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📤 Экспорт контактов",
            callback_data=f"{CallbackPrefixes.ADMIN}:export"
        )
    )
    return builder.as_markup()


# =============================================================================
# УТИЛИТЫ ДЛЯ РАБОТЫ С КЛАВИАТУРАМИ
# =============================================================================

def remove_keyboard() -> None:
    """
    Возвращает None для удаления клавиатуры.
    Используется при редактировании сообщения для деактивации кнопок.
    
    Usage:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    """
    return None


def get_single_button_keyboard(text: str, callback_data: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с одной кнопкой.
    Универсальный метод для простых случаев.
    
    Args:
        text: Текст кнопки
        callback_data: Callback data
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=text, callback_data=callback_data)
    )
    return builder.as_markup()


def get_url_button_keyboard(text: str, url: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с URL-кнопкой.
    
    Args:
        text: Текст кнопки
        url: URL для перехода
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=text, url=url)
    )
    return builder.as_markup()


def parse_callback_data(callback_data: str) -> tuple[str, list[str]]:
    """
    Парсит callback_data на префикс и параметры.
    
    Args:
        callback_data: Строка вида "prefix:action:param1:param2"
    
    Returns:
        Tuple[prefix, [action, param1, param2, ...]]
    """
    parts = callback_data.split(":")
    prefix = parts[0] if parts else ""
    params = parts[1:] if len(parts) > 1 else []
    return prefix, params


# =============================================================================
# ДИНАМИЧЕСКИЕ КЛАВИАТУРЫ
# =============================================================================

def get_yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Универсальная клавиатура Да/Нет."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=yes_callback),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_callback)
    )
    return builder.as_markup()


def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Назад."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)
    )
    return builder.as_markup()


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str
) -> InlineKeyboardMarkup:
    """
    Клавиатура пагинации.
    
    Args:
        current_page: Текущая страница (начиная с 1)
        total_pages: Всего страниц
        prefix: Префикс для callback_data
    """
    builder = InlineKeyboardBuilder()
    buttons = []
    
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{prefix}:page:{current_page - 1}"
            )
        )
    
    buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data=f"{prefix}:current"
        )
    )
    
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{prefix}:page:{current_page + 1}"
            )
        )
    
    builder.row(*buttons)
    return builder.as_markup()
