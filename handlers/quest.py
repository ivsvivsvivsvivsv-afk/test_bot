"""
Обработчики квеста (выбор класса, оружия, раунды).

Особенности:
- FSM для управления состоянием
- Последовательная отправка сообщений
- Деактивация кнопок после нажатия
- Сохранение прогресса в базу
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Database
from texts import TEXTS
from keyboards.inline import (
    CallbackPrefixes,
    remove_keyboard,
    get_quest_continue_keyboard,
)
from utils.statements import (
    get_statement_for_round,
    get_statement_text_formatted,
    get_wisdom_text,
    Statement,
)
from utils.notifications import notify_quest_completed

logger = logging.getLogger(__name__)

router = Router(name="quest")


# =============================================================================
# FSM СОСТОЯНИЯ
# =============================================================================

class QuestStates(StatesGroup):
    """Состояния квеста."""
    selecting_class = State()
    selecting_weapon = State()
    playing_round = State()
    viewing_result = State()


# =============================================================================
# КЛАССЫ И ОРУЖИЯ
# =============================================================================

HERO_CLASSES = {
    "businessman": {
        "name": "💼 Бизнесмен",
        "emoji": "💼",
        "description": "Строит империю с помощью ИИ"
    },
    "creator": {
        "name": "🎨 Творец",
        "emoji": "🎨",
        "description": "Создает контент с помощью ИИ"
    },
    "analyst": {
        "name": "📊 Аналитик",
        "emoji": "📊",
        "description": "Анализирует данные с помощью ИИ"
    },
    "manager": {
        "name": "📋 Менеджер",
        "emoji": "📋",
        "description": "Управляет проектами с ИИ"
    }
}

WEAPONS = {
    "marketing": {
        "name": "📈 Меч Маркетинга",
        "emoji": "📈",
        "description": "Продвижение и реклама"
    },
    "analytics": {
        "name": "🔍 Линза Аналитики",
        "emoji": "🔍",
        "description": "Данные и аналитика"
    },
    "copywriting": {
        "name": "✍️ Перо Копирайтинга",
        "emoji": "✍️",
        "description": "Тексты и контент"
    },
    "design": {
        "name": "🎨 Кисть Дизайна",
        "emoji": "🎨",
        "description": "Визуальный контент"
    },
    "management": {
        "name": "📋 Скрижаль Менеджмента",
        "emoji": "📋",
        "description": "Управление и процессы"
    },
    "video": {
        "name": "🎬 Камера Видео",
        "emoji": "🎬",
        "description": "Видеоконтент"
    }
}


# =============================================================================
# КЛАВИАТУРЫ
# =============================================================================

def get_class_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора класса."""
    builder = InlineKeyboardBuilder()
    
    for class_id, class_info in HERO_CLASSES.items():
        builder.row(
            InlineKeyboardButton(
                text=f"{class_info['emoji']} {class_info['name'].split()[1]}",
                callback_data=f"{CallbackPrefixes.QUEST}:class:{class_id}"
            )
        )
    
    return builder.as_markup()


def get_weapon_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора оружия."""
    builder = InlineKeyboardBuilder()
    
    for weapon_id, weapon_info in WEAPONS.items():
        builder.row(
            InlineKeyboardButton(
                text=weapon_info['name'],
                callback_data=f"{CallbackPrefixes.QUEST}:weapon:{weapon_id}"
            )
        )
    
    return builder.as_markup()


def get_answer_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ответа на утверждение (Правда/Ложь)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Правда",
            callback_data=f"{CallbackPrefixes.QUEST}:answer:true"
        ),
        InlineKeyboardButton(
            text="❌ Ложь",
            callback_data=f"{CallbackPrefixes.QUEST}:answer:false"
        )
    )
    return builder.as_markup()


def get_next_round_keyboard(is_last: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура перехода к следующему раунду."""
    builder = InlineKeyboardBuilder()
    
    if is_last:
        builder.row(
            InlineKeyboardButton(
                text="🏆 Узнать результат",
                callback_data=f"{CallbackPrefixes.QUEST}:show_result"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="➡️ Следующий раунд",
                callback_data=f"{CallbackPrefixes.QUEST}:next_round"
            )
        )
    
    return builder.as_markup()


def get_finish_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после результатов."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎁 Получить подарок",
            callback_data=f"{CallbackPrefixes.QUEST}:get_prize"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Пройти снова",
            callback_data=f"{CallbackPrefixes.QUEST}:restart"
        )
    )
    return builder.as_markup()


# =============================================================================
# ПОКАЗ ВЫБОРА КЛАССА
# =============================================================================

async def show_class_selection(message: Message, state: FSMContext, db: Database):
    """Показывает выбор класса героя."""
    await state.set_state(QuestStates.selecting_class)
    
    await message.answer(
        TEXTS["select_class"],
        parse_mode="HTML",
        reply_markup=get_class_keyboard()
    )


# =============================================================================
# ВЫБОР КЛАССА
# =============================================================================

@router.callback_query(F.data.startswith(f"{CallbackPrefixes.QUEST}:class:"))
async def cb_select_class(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработка выбора класса."""
    user_id = callback.from_user.id
    class_id = callback.data.split(":")[-1]
    
    if class_id not in HERO_CLASSES:
        await callback.answer("Неизвестный класс", show_alert=True)
        return
    
    class_info = HERO_CLASSES[class_id]
    logger.info(f"User {user_id} selected class: {class_id}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer(f"Вы выбрали: {class_info['name']}")
    
    # Сохраняем в FSM и базу
    await state.update_data(hero_class=class_id)
    await db.update_user_class(user_id, class_id)
    
    # Отправляем подтверждение и переходим к выбору оружия
    await callback.message.answer(
        f"⚔️ <b>Отлично! Вы — {class_info['name']}</b>\n\n"
        f"{class_info['description']}\n\n"
        "Теперь выберите своё оружие — специализацию в мире ИИ:",
        parse_mode="HTML",
        reply_markup=get_weapon_keyboard()
    )
    
    await state.set_state(QuestStates.selecting_weapon)


# =============================================================================
# ВЫБОР ОРУЖИЯ
# =============================================================================

@router.callback_query(F.data.startswith(f"{CallbackPrefixes.QUEST}:weapon:"))
async def cb_select_weapon(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработка выбора оружия."""
    user_id = callback.from_user.id
    weapon_id = callback.data.split(":")[-1]
    
    if weapon_id not in WEAPONS:
        await callback.answer("Неизвестное оружие", show_alert=True)
        return
    
    weapon_info = WEAPONS[weapon_id]
    logger.info(f"User {user_id} selected weapon: {weapon_id}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer(f"Вы выбрали: {weapon_info['name']}")
    
    # Сохраняем в FSM и базу
    await state.update_data(weapon=weapon_id, current_round=1, score=0)
    await db.update_user_weapon(user_id, weapon_id)
    
    # Отправляем подтверждение
    await callback.message.answer(
        f"🗡️ <b>Ваше оружие: {weapon_info['name']}</b>\n\n"
        f"{weapon_info['description']}\n\n"
        "Приготовьтесь! Сейчас начнётся испытание.\n"
        "Вам нужно определить: правда или ложь перед вами.",
        parse_mode="HTML"
    )
    
    # Небольшая пауза и начинаем первый раунд
    await start_round(callback.message, state, db, user_id, 1)


# =============================================================================
# ЗАПУСК РАУНДА
# =============================================================================

async def start_round(message: Message, state: FSMContext, db: Database, user_id: int, round_num: int):
    """Запускает раунд квеста."""
    data = await state.get_data()
    weapon = data.get("weapon", "other")
    
    # Получаем утверждение
    statement = get_statement_for_round(weapon, round_num)
    
    if not statement:
        logger.error(f"No statement found for weapon={weapon}, round={round_num}")
        await message.answer("Произошла ошибка. Попробуйте /restart")
        return
    
    # Сохраняем текущее утверждение в FSM для проверки ответа
    await state.update_data(
        current_round=round_num,
        current_statement_text=statement.text,
        current_statement_is_truth=statement.is_truth,
        current_statement_wisdom=statement.wisdom_prompt
    )
    
    # Обновляем базу
    await db.update_user_round(user_id, round_num)
    
    await state.set_state(QuestStates.playing_round)
    
    # Отправляем утверждение
    text = get_statement_text_formatted(statement, round_num)
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_answer_keyboard()
    )


# =============================================================================
# ОТВЕТ НА УТВЕРЖДЕНИЕ
# =============================================================================

@router.callback_query(F.data.startswith(f"{CallbackPrefixes.QUEST}:answer:"))
async def cb_answer(callback: CallbackQuery, state: FSMContext, db: Database):
    """Обработка ответа на утверждение."""
    user_id = callback.from_user.id
    answer = callback.data.split(":")[-1]  # "true" или "false"
    user_said_true = answer == "true"
    
    # Получаем данные из FSM
    data = await state.get_data()
    current_round = data.get("current_round", 1)
    is_truth = data.get("current_statement_is_truth", True)
    statement_text = data.get("current_statement_text", "")
    wisdom_prompt = data.get("current_statement_wisdom", "")
    score = data.get("score", 0)
    
    # Проверяем правильность
    is_correct = user_said_true == is_truth
    
    if is_correct:
        score += 1
        await state.update_data(score=score)
        await db.update_user_score(user_id, score)
    
    logger.info(f"User {user_id} answered round {current_round}: correct={is_correct}, score={score}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("✅ Правильно!" if is_correct else "❌ Неверно!")
    
    # Создаем Statement объект для get_wisdom_text
    statement = Statement(
        text=statement_text,
        is_truth=is_truth,
        wisdom_prompt=wisdom_prompt,
        level=current_round
    )
    
    # Отправляем результат с объяснением
    wisdom_text = get_wisdom_text(statement, is_correct)
    is_last_round = current_round >= 3
    
    await callback.message.answer(
        wisdom_text,
        parse_mode="HTML",
        reply_markup=get_next_round_keyboard(is_last=is_last_round)
    )


# =============================================================================
# ПЕРЕХОД К СЛЕДУЮЩЕМУ РАУНДУ
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.QUEST}:next_round")
async def cb_next_round(callback: CallbackQuery, state: FSMContext, db: Database):
    """Переход к следующему раунду."""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_round = data.get("current_round", 1)
    next_round = current_round + 1
    
    logger.info(f"User {user_id} moving to round {next_round}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Запускаем следующий раунд
    await start_round(callback.message, state, db, user_id, next_round)


# =============================================================================
# ПОКАЗ РЕЗУЛЬТАТА
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.QUEST}:show_result")
async def cb_show_result(callback: CallbackQuery, state: FSMContext, db: Database):
    """Показывает итоговый результат квеста."""
    user_id = callback.from_user.id
    data = await state.get_data()
    score = data.get("score", 0)
    weapon = data.get("weapon", "other")
    hero_class = data.get("hero_class", "businessman")
    
    logger.info(f"User {user_id} completed quest with score {score}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("🏆 Квест завершен!")
    
    # Определяем результат
    if score == 3:
        result_text = TEXTS["result_perfect"]
        result_emoji = "🏆"
    elif score == 2:
        result_text = TEXTS["result_good"]
        result_emoji = "🎖️"
    elif score == 1:
        result_text = TEXTS["result_ok"]
        result_emoji = "🥉"
    else:
        result_text = TEXTS["result_bad"]
        result_emoji = "💪"
    
    # Получаем название оружия
    weapon_name = WEAPONS.get(weapon, {}).get("name", "Неизвестное оружие")
    class_name = HERO_CLASSES.get(hero_class, {}).get("name", "Герой")
    
    # Формируем итоговое сообщение
    final_text = (
        f"{result_emoji} <b>Квест завершён!</b>\n\n"
        f"🎭 Класс: {class_name}\n"
        f"⚔️ Оружие: {weapon_name}\n"
        f"⭐ Очки: {score}/3\n\n"
        f"{result_text}"
    )
    
    # Отмечаем квест как пройденный
    await db.complete_quest(user_id, score)
    await state.set_state(QuestStates.viewing_result)
    
    await callback.message.answer(
        final_text,
        parse_mode="HTML",
        reply_markup=get_finish_keyboard()
    )
    
    # Уведомляем админов
    await notify_quest_completed(
        bot=callback.bot,
        user_id=user_id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
        result=weapon_name,
        score=score
    )


# =============================================================================
# ПОЛУЧЕНИЕ ПРИЗА (ПЕРЕХОД К КОНТАКТАМ)
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.QUEST}:get_prize")
async def cb_get_prize(callback: CallbackQuery, state: FSMContext, db: Database):
    """Переход к сбору контактов для получения приза."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} wants to get prize")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Импортируем здесь чтобы избежать циклического импорта
    from handlers.contacts import start_contact_collection
    
    # Запускаем сбор контактов
    await start_contact_collection(callback.message, state, db, user_id)


# =============================================================================
# РЕСТАРТ КВЕСТА
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.QUEST}:restart")
async def cb_restart_quest(callback: CallbackQuery, state: FSMContext, db: Database):
    """Перезапуск квеста."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} restarting quest")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("🔄 Начинаем заново!")
    
    # Сбрасываем состояние
    await state.clear()
    await db.reset_user_progress(user_id)
    
    # Показываем выбор класса
    await show_class_selection(callback.message, state, db)
