from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from texts import BUTTONS


def kb_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["start_quest"], callback_data="start_quest")
    b.button(text=BUTTONS["open_generator"], callback_data="open_generator")
    b.button(text=BUTTONS["arena_signup"], callback_data="arena_signup")
    b.adjust(1)
    return b.as_markup()


def kb_class() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["class_boss"], callback_data="class_boss")
    b.button(text=BUTTONS["class_freelancer"], callback_data="class_freelancer")
    b.adjust(1)
    return b.as_markup()


def kb_weapon() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["weapon_marketing"], callback_data="weapon_marketing")
    b.button(text=BUTTONS["weapon_analytics"], callback_data="weapon_analytics")
    b.button(text=BUTTONS["weapon_copywriting"], callback_data="weapon_copywriting")
    b.button(text=BUTTONS["weapon_design"], callback_data="weapon_design")
    b.button(text=BUTTONS["weapon_management"], callback_data="weapon_management")
    b.button(text=BUTTONS["weapon_video"], callback_data="weapon_video")
    b.button(text=BUTTONS["weapon_other"], callback_data="weapon_other")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def kb_go_check() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["go_check"], callback_data="go_check")
    b.adjust(1)
    return b.as_markup()


def kb_answer() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["answer_true"], callback_data="answer_true")
    b.button(text=BUTTONS["answer_false"], callback_data="answer_false")
    b.adjust(1)
    return b.as_markup()


def kb_next_round(next_round: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["next_round"], callback_data=f"next_round_{next_round}")
    b.adjust(1)
    return b.as_markup()


def kb_show_moral() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["show_moral"], callback_data="show_moral")
    b.adjust(1)
    return b.as_markup()


def kb_want_workshop() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["want_workshop"], callback_data="want_workshop")
    b.adjust(1)
    return b.as_markup()
