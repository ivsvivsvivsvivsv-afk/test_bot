"""Keyboards package."""

from keyboards.inline import (
    CallbackPrefixes,
    # Стартовые
    get_start_keyboard,
    get_continue_keyboard,
    # Квест
    get_quest_start_keyboard,
    get_quest_choice_keyboard,
    get_quest_continue_keyboard,
    get_quest_result_keyboard,
    get_quest_finish_keyboard,
    # Арена
    get_arena_start_keyboard,
    get_arena_specialization_keyboard,
    get_arena_task_keyboard,
    get_arena_result_keyboard,
    # Контакты
    get_contact_start_keyboard,
    get_contact_phone_keyboard,
    get_contact_email_keyboard,
    get_contact_confirm_keyboard,
    get_contact_success_keyboard,
    # Админ
    get_admin_keyboard,
    # Утилиты
    remove_keyboard,
    get_single_button_keyboard,
    get_url_button_keyboard,
    parse_callback_data,
    get_yes_no_keyboard,
    get_back_keyboard,
    get_pagination_keyboard,
)

__all__ = [
    "CallbackPrefixes",
    "get_start_keyboard",
    "get_continue_keyboard",
    "get_quest_start_keyboard",
    "get_quest_choice_keyboard",
    "get_quest_continue_keyboard",
    "get_quest_result_keyboard",
    "get_quest_finish_keyboard",
    "get_arena_start_keyboard",
    "get_arena_specialization_keyboard",
    "get_arena_task_keyboard",
    "get_arena_result_keyboard",
    "get_contact_start_keyboard",
    "get_contact_phone_keyboard",
    "get_contact_email_keyboard",
    "get_contact_confirm_keyboard",
    "get_contact_success_keyboard",
    "get_admin_keyboard",
    "remove_keyboard",
    "get_single_button_keyboard",
    "get_url_button_keyboard",
    "parse_callback_data",
    "get_yes_no_keyboard",
    "get_back_keyboard",
    "get_pagination_keyboard",
]
