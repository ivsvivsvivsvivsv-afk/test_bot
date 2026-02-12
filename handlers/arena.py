"""
Обработчики арены (дополнительный путь с заданиями).

Особенности:
- FSM состояния для управления потоком
- Выбор специализации
- Выполнение заданий
- Последовательная отправка сообщений
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
from keyboards.inline import CallbackPrefixes, remove_keyboard
from utils.notifications import notify_arena_completed

logger = logging.getLogger(__name__)

router = Router(name="arena")


# =============================================================================
# FSM СОСТОЯНИЯ
# =============================================================================

class ArenaStates(StatesGroup):
    """Состояния арены."""
    selecting_spec = State()     # Выбор специализации
    doing_task = State()         # Выполнение задания
    waiting_response = State()   # Ожидание ответа на задание
    viewing_result = State()     # Просмотр результата


# =============================================================================
# СПЕЦИАЛИЗАЦИИ И ЗАДАНИЯ
# =============================================================================

ARENA_SPECS = {
    "marketing": {
        "name": "📊 Маркетинг",
        "emoji": "📊",
        "tasks": [
            {
                "id": 1,
                "title": "Анализ конкурента",
                "description": "Используя Perplexity, найдите 3 сильные стороны маркетинга компании Apple.",
                "hint": "Попробуй промт: 'Какие маркетинговые стратегии Apple наиболее эффективны?'"
            },
            {
                "id": 2,
                "title": "Креативный контент",
                "description": "С помощью ChatGPT придумайте 5 идей для вирусного поста в Instagram.",
                "hint": "Уточните нишу и целевую аудиторию в промте"
            }
        ]
    },
    "analytics": {
        "name": "📈 Аналитика",
        "emoji": "📈",
        "tasks": [
            {
                "id": 1,
                "title": "Анализ данных",
                "description": "Попросите ChatGPT проанализировать гипотетический набор данных о продажах.",
                "hint": "Опишите структуру данных и задайте конкретные вопросы"
            },
            {
                "id": 2,
                "title": "Построение отчёта",
                "description": "Создайте структуру аналитического отчёта с помощью Claude.",
                "hint": "Укажите цель отчёта и целевую аудиторию"
            }
        ]
    },
    "copywriting": {
        "name": "✍️ Копирайтинг",
        "emoji": "✍️",
        "tasks": [
            {
                "id": 1,
                "title": "Продающий текст",
                "description": "Напишите продающий заголовок для курса по нейросетям с помощью ChatGPT.",
                "hint": "Используйте формулу AIDA или PAS"
            },
            {
                "id": 2,
                "title": "Email-рассылка",
                "description": "Создайте цепочку из 3 писем для прогрева аудитории.",
                "hint": "Укажите продукт и боли целевой аудитории"
            }
        ]
    },
    "design": {
        "name": "🎨 Дизайн",
        "emoji": "🎨",
        "tasks": [
            {
                "id": 1,
                "title": "Генерация изображения",
                "description": "Создайте промт для Midjourney для логотипа IT-компании.",
                "hint": "Укажите стиль, цвета, настроение"
            },
            {
                "id": 2,
                "title": "Визуальная концепция",
                "description": "Опишите визуальный стиль для landing page с помощью ChatGPT.",
                "hint": "Укажите нишу и целевую аудиторию"
            }
        ]
    }
}


# =============================================================================
# КЛАВИАТУРЫ
# =============================================================================

def get_arena_intro_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура входа на арену."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⚔️ Войти на Арену",
            callback_data=f"{CallbackPrefixes.ARENA}:enter"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"{CallbackPrefixes.ARENA}:back"
        )
    )
    return builder.as_markup()


def get_spec_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора специализации."""
    builder = InlineKeyboardBuilder()
    
    for spec_id, spec_info in ARENA_SPECS.items():
        builder.row(
            InlineKeyboardButton(
                text=spec_info["name"],
                callback_data=f"{CallbackPrefixes.ARENA}:spec:{spec_id}"
            )
        )
    
    return builder.as_markup()


def get_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для задания."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Задание выполнено",
            callback_data=f"{CallbackPrefixes.ARENA}:complete:{task_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💡 Подсказка",
            callback_data=f"{CallbackPrefixes.ARENA}:hint:{task_id}"
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
    """Клавиатура после завершения арены."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎁 Получить приз",
            callback_data=f"{CallbackPrefixes.ARENA}:claim_prize"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Пройти ещё раз",
            callback_data=f"{CallbackPrefixes.ARENA}:restart"
        )
    )
    return builder.as_markup()


# =============================================================================
# ОБРАБОТЧИКИ
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.ARENA}:enter")
async def cb_enter_arena(callback: CallbackQuery, state: FSMContext):
    """Вход на арену."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} entering arena")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("⚔️ Добро пожаловать на Арену!")
    
    # Устанавливаем состояние
    await state.set_state(ArenaStates.selecting_spec)
    await state.update_data(tasks_completed=0, total_tasks=0)
    
    await callback.message.answer(
        TEXTS["arena_intro"],
        parse_mode="HTML",
        reply_markup=get_spec_keyboard()
    )


@router.callback_query(F.data.startswith(f"{CallbackPrefixes.ARENA}:spec:"))
async def cb_select_spec(callback: CallbackQuery, state: FSMContext, db: Database):
    """Выбор специализации на арене."""
    user_id = callback.from_user.id
    spec_id = callback.data.split(":")[-1]
    
    if spec_id not in ARENA_SPECS:
        await callback.answer("Неизвестная специализация", show_alert=True)
        return
    
    spec_info = ARENA_SPECS[spec_id]
    logger.info(f"User {user_id} selected arena spec: {spec_id}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer(f"Вы выбрали: {spec_info['name']}")
    
    # Сохраняем в FSM
    tasks = spec_info["tasks"]
    await state.update_data(
        arena_spec=spec_id,
        current_task_index=0,
        total_tasks=len(tasks),
        tasks_completed=0
    )
    
    # Обновляем базу
    await db.update_user_arena_spec(user_id, spec_id)
    
    # Отправляем первое задание
    await send_task(callback.message, state, 0, spec_id)


async def send_task(message: Message, state: FSMContext, task_index: int, spec_id: str):
    """Отправляет задание."""
    spec = ARENA_SPECS.get(spec_id)
    if not spec:
        await message.answer("Ошибка: специализация не найдена")
        return
    
    tasks = spec["tasks"]
    
    if task_index >= len(tasks):
        # Все задания выполнены
        await show_arena_result(message, state)
        return
    
    task = tasks[task_index]
    
    await state.set_state(ArenaStates.doing_task)
    await state.update_data(current_task_index=task_index, current_task_id=task["id"])
    
    await message.answer(
        f"📋 <b>Задание {task_index + 1}/{len(tasks)}: {task['title']}</b>\n\n"
        f"{task['description']}",
        parse_mode="HTML",
        reply_markup=get_task_keyboard(task["id"])
    )


@router.callback_query(F.data.startswith(f"{CallbackPrefixes.ARENA}:complete:"))
async def cb_complete_task(callback: CallbackQuery, state: FSMContext, db: Database):
    """Задание выполнено."""
    user_id = callback.from_user.id
    task_id = int(callback.data.split(":")[-1])
    
    data = await state.get_data()
    task_index = data.get("current_task_index", 0)
    spec_id = data.get("arena_spec", "marketing")
    tasks_completed = data.get("tasks_completed", 0) + 1
    
    logger.info(f"User {user_id} completed task {task_id}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("✅ Отлично!")
    
    # Обновляем счетчик
    await state.update_data(tasks_completed=tasks_completed)
    
    # Отправляем подтверждение и следующее задание
    await callback.message.answer(
        "✅ <b>Задание засчитано!</b>\n\n"
        "Переходим к следующему...",
        parse_mode="HTML"
    )
    
    # Следующее задание
    await send_task(callback.message, state, task_index + 1, spec_id)


@router.callback_query(F.data.startswith(f"{CallbackPrefixes.ARENA}:hint:"))
async def cb_show_hint(callback: CallbackQuery, state: FSMContext):
    """Показать подсказку."""
    task_id = int(callback.data.split(":")[-1])
    
    data = await state.get_data()
    spec_id = data.get("arena_spec", "marketing")
    task_index = data.get("current_task_index", 0)
    
    spec = ARENA_SPECS.get(spec_id)
    if not spec or task_index >= len(spec["tasks"]):
        await callback.answer("Подсказка недоступна", show_alert=True)
        return
    
    task = spec["tasks"][task_index]
    hint = task.get("hint", "Подсказка не найдена")
    
    await callback.answer(f"💡 {hint}", show_alert=True)


@router.callback_query(F.data.startswith(f"{CallbackPrefixes.ARENA}:skip:"))
async def cb_skip_task(callback: CallbackQuery, state: FSMContext):
    """Пропустить задание."""
    user_id = callback.from_user.id
    
    data = await state.get_data()
    task_index = data.get("current_task_index", 0)
    spec_id = data.get("arena_spec", "marketing")
    
    logger.info(f"User {user_id} skipped task {task_index + 1}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("⏭️ Задание пропущено")
    
    # Следующее задание без увеличения счетчика
    await send_task(callback.message, state, task_index + 1, spec_id)


async def show_arena_result(message: Message, state: FSMContext):
    """Показывает результат арены."""
    data = await state.get_data()
    tasks_completed = data.get("tasks_completed", 0)
    total_tasks = data.get("total_tasks", 0)
    spec_id = data.get("arena_spec", "marketing")
    
    spec_name = ARENA_SPECS.get(spec_id, {}).get("name", "Специализация")
    
    await state.set_state(ArenaStates.viewing_result)
    
    if tasks_completed == total_tasks:
        result_text = "🏆 <b>Превосходно!</b> Вы выполнили все задания!"
    elif tasks_completed > 0:
        result_text = f"🎖️ <b>Неплохо!</b> Вы выполнили {tasks_completed} из {total_tasks} заданий."
    else:
        result_text = "💪 <b>Попробуйте ещё раз!</b> Практика — ключ к мастерству."
    
    await message.answer(
        f"⚔️ <b>Арена завершена!</b>\n\n"
        f"🎯 Специализация: {spec_name}\n"
        f"✅ Выполнено заданий: {tasks_completed}/{total_tasks}\n\n"
        f"{result_text}",
        parse_mode="HTML",
        reply_markup=get_arena_result_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.ARENA}:claim_prize")
async def cb_claim_prize(callback: CallbackQuery, state: FSMContext, db: Database):
    """Получение приза после арены."""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    logger.info(f"User {user_id} claiming arena prize")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Уведомляем админов
    await notify_arena_completed(
        bot=callback.bot,
        user_id=user_id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
        specialization=data.get("arena_spec", "unknown"),
        tasks_completed=data.get("tasks_completed", 0),
        total_tasks=data.get("total_tasks", 0)
    )
    
    # Переходим к сбору контактов
    from handlers.contacts import start_contact_collection
    await start_contact_collection(callback.message, state, db, user_id)


@router.callback_query(F.data == f"{CallbackPrefixes.ARENA}:restart")
async def cb_restart_arena(callback: CallbackQuery, state: FSMContext):
    """Перезапуск арены."""
    logger.info(f"User {callback.from_user.id} restarting arena")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("🔄 Начинаем заново!")
    
    # Сбрасываем состояние арены
    await state.set_state(ArenaStates.selecting_spec)
    await state.update_data(tasks_completed=0, total_tasks=0)
    
    await callback.message.answer(
        TEXTS["arena_intro"],
        parse_mode="HTML",
        reply_markup=get_spec_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.ARENA}:back")
async def cb_arena_back(callback: CallbackQuery, state: FSMContext):
    """Возврат из арены."""
    logger.info(f"User {callback.from_user.id} leaving arena")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    await state.clear()
    
    from keyboards.inline import get_start_keyboard
    
    await callback.message.answer(
        TEXTS["welcome"],
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )
