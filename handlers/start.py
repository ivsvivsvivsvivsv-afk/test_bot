"""
Обработчики команды /start и начального флоу.

Особенности:
- Последовательная отправка сообщений (answer() вместо edit_text() где нужно)
- Деактивация кнопок после нажатия
- Обработка глубоких ссылок (utm_source)
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from database import Database
from texts import TEXTS
from keyboards.inline import (
    CallbackPrefixes,
    get_start_keyboard,
    get_continue_keyboard,
    remove_keyboard,
)
from utils.notifications import notify_new_user

logger = logging.getLogger(__name__)

router = Router(name="start")


# =============================================================================
# КОМАНДА /START
# =============================================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database):
    """
    Обработка команды /start.
    Поддерживает глубокие ссылки: /start utm_tiktok
    """
    user = message.from_user
    user_id = user.id
    
    # Извлекаем utm_source из глубокой ссылки
    args = message.text.split(maxsplit=1)
    source = args[1] if len(args) > 1 else None
    
    logger.info(f"User {user_id} started bot, source: {source}")
    
    # Очищаем состояние FSM для чистого старта
    await state.clear()
    
    # Проверяем, есть ли пользователь в базе
    existing_user = await db.get_user(user_id)
    
    if existing_user:
        # Пользователь уже был, обновляем last_activity
        await db.update_user_activity(user_id)
        logger.info(f"Returning user {user_id}")
        
        # Проверяем, проходил ли квест
        if existing_user.get("quest_completed"):
            # Показываем сообщение о возвращении
            await message.answer(
                TEXTS["welcome_back"],
                parse_mode="HTML"
            )
            return
    else:
        # Новый пользователь
        await db.add_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            source=source
        )
        logger.info(f"New user {user_id} registered, source: {source}")
        
        # Уведомляем админов о новом пользователе
        await notify_new_user(
            bot=message.bot,
            user_id=user_id,
            username=user.username,
            full_name=user.full_name,
            source=source
        )
    
    # Отправляем приветственное сообщение с клавиатурой
    await message.answer(
        TEXTS["welcome"],
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )


# =============================================================================
# ОБРАБОТКА КНОПОК СТАРТОВОГО МЕНЮ
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.START}:begin_quest")
async def cb_begin_quest(callback: CallbackQuery, state: FSMContext, db: Database):
    """
    Начало квеста.
    Деактивируем кнопки и переходим к выбору класса.
    """
    user_id = callback.from_user.id
    logger.info(f"User {user_id} clicked begin_quest")
    
    # ВАЖНО: Деактивируем кнопки на предыдущем сообщении
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    # Подтверждаем callback чтобы убрать "часики"
    await callback.answer()
    
    # Отправляем НОВОЕ сообщение (не редактируем) для четкой последовательности
    await callback.message.answer(
        TEXTS["quest_intro"],
        parse_mode="HTML",
        reply_markup=get_continue_keyboard()
    )
    
    # Обновляем статус в базе
    await db.update_user_step(user_id, "quest_intro")


@router.callback_query(F.data == f"{CallbackPrefixes.START}:about_course")
async def cb_about_course(callback: CallbackQuery):
    """Информация о курсе."""
    logger.info(f"User {callback.from_user.id} clicked about_course")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Отправляем информацию о курсе
    await callback.message.answer(
        TEXTS["about_course"],
        parse_mode="HTML",
        reply_markup=get_start_keyboard()  # Снова показываем стартовые кнопки
    )


@router.callback_query(F.data == f"{CallbackPrefixes.START}:continue")
async def cb_continue_to_class(callback: CallbackQuery, state: FSMContext, db: Database):
    """
    Переход к выбору класса после вводной информации.
    """
    user_id = callback.from_user.id
    logger.info(f"User {user_id} continues to class selection")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Импортируем здесь чтобы избежать циклического импорта
    from handlers.quest import show_class_selection
    
    # Показываем выбор класса
    await show_class_selection(callback.message, state, db)


# =============================================================================
# КОМАНДА /HELP
# =============================================================================

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает справку."""
    await message.answer(
        TEXTS["help"],
        parse_mode="HTML"
    )


# =============================================================================
# КОМАНДА /RESTART
# =============================================================================

@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext, db: Database):
    """
    Перезапуск квеста.
    Сбрасывает прогресс пользователя.
    """
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested restart")
    
    # Сбрасываем FSM состояние
    await state.clear()
    
    # Сбрасываем прогресс в базе (но не удаляем пользователя)
    await db.reset_user_progress(user_id)
    
    await message.answer(
        TEXTS["restart_confirm"],
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )


# =============================================================================
# КОМАНДА /STATUS
# =============================================================================

@router.message(Command("status"))
async def cmd_status(message: Message, db: Database):
    """
    Показывает текущий статус пользователя.
    """
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer(
            "Вы еще не начали квест. Нажмите /start",
            parse_mode="HTML"
        )
        return
    
    # Формируем статус
    status_parts = []
    
    if user_data.get("hero_class"):
        status_parts.append(f"🎭 Класс: {user_data['hero_class']}")
    
    if user_data.get("weapon"):
        status_parts.append(f"⚔️ Оружие: {user_data['weapon']}")
    
    if user_data.get("current_round"):
        status_parts.append(f"🎯 Раунд: {user_data['current_round']}/3")
    
    if user_data.get("score") is not None:
        status_parts.append(f"⭐ Очки: {user_data['score']}")
    
    if user_data.get("quest_completed"):
        status_parts.append("✅ Квест пройден!")
    
    if not status_parts:
        status_parts.append("Квест еще не начат")
    
    status_text = "\n".join(status_parts)
    
    await message.answer(
        f"<b>📊 Ваш статус:</b>\n\n{status_text}",
        parse_mode="HTML"
    )
