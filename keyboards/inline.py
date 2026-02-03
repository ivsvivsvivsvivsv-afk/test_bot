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
    b.button(text="⬅️ Назад", callback_data="back_to_start")
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
    b.button(text="⬅️ Назад", callback_data="back_to_class")
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def kb_go_check() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["go_check"], callback_data="go_check")
    b.button(text="⬅️ Назад", callback_data="back_to_weapon")
    b.adjust(1)
    return b.as_markup()


def kb_answer() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["answer_true"], callback_data="answer_true")
    b.button(text=BUTTONS["answer_false"], callback_data="answer_false")
    b.button(text="⬅️ Назад к вопросу", callback_data="back_to_question")
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

def kb_open_generator() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS["open_generator"], callback_data="open_generator")
    b.adjust(1)
    return b.as_markup()


def kb_go_to_quest() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # reuse existing start_quest handler
    b.button(text=BUTTONS.get("go_to_quest", BUTTONS["start_quest"]), callback_data="start_quest")
    b.adjust(1)
    return b.as_markup()


def kb_already_played() -> InlineKeyboardMarkup:
    """Keyboard for users who already completed the quest."""
    b = InlineKeyboardBuilder()
    b.button(text=BUTTONS.get("signup_workshop", "🚀 Записаться на воркшоп"), callback_data="signup_workshop_direct")
    b.button(text=BUTTONS["open_generator"], callback_data="open_generator")
    b.button(text=BUTTONS["arena_signup"], callback_data="arena_signup")
    b.adjust(1)
    return b.as_markup()

