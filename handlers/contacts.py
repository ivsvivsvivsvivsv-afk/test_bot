"""
Обработчики сбора контактных данных.

Особенности:
- FSM состояния для управления потоком (НЕ catch-all обработчики)
- Валидация телефона (Россия +7, Беларусь +375)
- Валидация email
- Понятные сообщения об ошибках
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
from utils.validation import validate_phone, validate_email, ValidationResult
from utils.notifications import notify_new_contact

logger = logging.getLogger(__name__)

router = Router(name="contacts")


# =============================================================================
# FSM СОСТОЯНИЯ ДЛЯ СБОРА КОНТАКТОВ
# =============================================================================

class ContactStates(StatesGroup):
    """Состояния для сбора контактов."""
    waiting_phone = State()      # Ожидаем ввод телефона
    waiting_email = State()      # Ожидаем ввод email
    confirming = State()         # Подтверждение данных


# =============================================================================
# КЛАВИАТУРЫ
# =============================================================================

def get_start_contact_keyboard() -> InlineKeyboardMarkup:
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
            text="⏭️ Пропустить",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip_all"
        )
    )
    return builder.as_markup()


def get_skip_phone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при вводе телефона."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить телефон",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip_phone"
        )
    )
    return builder.as_markup()


def get_skip_email_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при вводе email."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⏭️ Пропустить email",
            callback_data=f"{CallbackPrefixes.CONTACT}:skip_email"
        )
    )
    return builder.as_markup()


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения данных."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"{CallbackPrefixes.CONTACT}:confirm"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить телефон",
            callback_data=f"{CallbackPrefixes.CONTACT}:edit_phone"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить email",
            callback_data=f"{CallbackPrefixes.CONTACT}:edit_email"
        )
    )
    return builder.as_markup()


def get_success_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после успешного сохранения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🎓 Узнать о курсе",
            callback_data=f"{CallbackPrefixes.CONTACT}:to_course"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 В начало",
            callback_data=f"{CallbackPrefixes.CONTACT}:to_start"
        )
    )
    return builder.as_markup()


# =============================================================================
# ЗАПУСК СБОРА КОНТАКТОВ
# =============================================================================

async def start_contact_collection(message: Message, state: FSMContext, db: Database, user_id: int):
    """
    Начинает процесс сбора контактов.
    Вызывается из quest.py после завершения квеста.
    """
    logger.info(f"Starting contact collection for user {user_id}")
    
    # Проверяем, есть ли уже контакты
    user_data = await db.get_user(user_id)
    
    if user_data and (user_data.get("phone") or user_data.get("email")):
        # Контакты уже есть
        await message.answer(
            "📱 У нас уже есть ваши контакты!\n\n"
            "Хотите обновить их?",
            parse_mode="HTML",
            reply_markup=get_start_contact_keyboard()
        )
    else:
        # Контактов нет
        await message.answer(
            TEXTS["contact_intro"],
            parse_mode="HTML",
            reply_markup=get_start_contact_keyboard()
        )


# =============================================================================
# ОБРАБОТКА КНОПОК
# =============================================================================

@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:start")
async def cb_start_contact(callback: CallbackQuery, state: FSMContext):
    """Начало сбора контактов - запрос телефона."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started contact collection")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Переходим в состояние ожидания телефона
    await state.set_state(ContactStates.waiting_phone)
    await state.update_data(phone=None, email=None)
    
    await callback.message.answer(
        TEXTS["contact_phone_request"],
        parse_mode="HTML",
        reply_markup=get_skip_phone_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:skip_phone")
async def cb_skip_phone(callback: CallbackQuery, state: FSMContext):
    """Пропуск ввода телефона."""
    logger.info(f"User {callback.from_user.id} skipped phone")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("Телефон пропущен")
    
    # Переходим к email
    await state.set_state(ContactStates.waiting_email)
    
    await callback.message.answer(
        TEXTS["contact_email_request"],
        parse_mode="HTML",
        reply_markup=get_skip_email_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:skip_email")
async def cb_skip_email(callback: CallbackQuery, state: FSMContext, db: Database):
    """Пропуск ввода email."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} skipped email")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("Email пропущен")
    
    # Показываем подтверждение
    await show_confirmation(callback.message, state, db, user_id)


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:skip_all")
async def cb_skip_all(callback: CallbackQuery, state: FSMContext):
    """Пропуск всего сбора контактов."""
    logger.info(f"User {callback.from_user.id} skipped all contacts")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    await state.clear()
    
    await callback.message.answer(
        TEXTS["contact_skipped"],
        parse_mode="HTML",
        reply_markup=get_success_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:edit_phone")
async def cb_edit_phone(callback: CallbackQuery, state: FSMContext):
    """Редактирование телефона."""
    logger.info(f"User {callback.from_user.id} wants to edit phone")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Возвращаемся к вводу телефона
    await state.set_state(ContactStates.waiting_phone)
    
    await callback.message.answer(
        TEXTS["contact_phone_request"],
        parse_mode="HTML",
        reply_markup=get_skip_phone_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:edit_email")
async def cb_edit_email(callback: CallbackQuery, state: FSMContext):
    """Редактирование email."""
    logger.info(f"User {callback.from_user.id} wants to edit email")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    # Возвращаемся к вводу email
    await state.set_state(ContactStates.waiting_email)
    
    await callback.message.answer(
        TEXTS["contact_email_request"],
        parse_mode="HTML",
        reply_markup=get_skip_email_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:confirm")
async def cb_confirm_contacts(callback: CallbackQuery, state: FSMContext, db: Database):
    """Подтверждение и сохранение контактов."""
    user_id = callback.from_user.id
    data = await state.get_data()
    phone = data.get("phone")
    email = data.get("email")
    
    logger.info(f"User {user_id} confirmed contacts: phone={phone}, email={email}")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer("✅ Контакты сохранены!")
    
    # Сохраняем в базу
    await db.update_user_contacts(user_id, phone, email)
    
    # Уведомляем админов
    user = callback.from_user
    await notify_new_contact(
        bot=callback.bot,
        user_id=user_id,
        username=user.username,
        full_name=user.full_name,
        phone=phone,
        email=email
    )
    
    # Очищаем состояние
    await state.clear()
    
    # Показываем успех
    await callback.message.answer(
        TEXTS["contact_success"],
        parse_mode="HTML",
        reply_markup=get_success_keyboard()
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:to_course")
async def cb_to_course(callback: CallbackQuery, state: FSMContext):
    """Переход к информации о курсе."""
    logger.info(f"User {callback.from_user.id} going to course info")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    
    await callback.message.answer(
        TEXTS["about_course"],
        parse_mode="HTML"
    )


@router.callback_query(F.data == f"{CallbackPrefixes.CONTACT}:to_start")
async def cb_to_start(callback: CallbackQuery, state: FSMContext):
    """Возврат в начало."""
    logger.info(f"User {callback.from_user.id} going to start")
    
    # Деактивируем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=remove_keyboard())
    except TelegramBadRequest as e:
        logger.warning(f"Could not remove keyboard: {e}")
    
    await callback.answer()
    await state.clear()
    
    # Импортируем здесь чтобы избежать циклического импорта
    from keyboards.inline import get_start_keyboard
    
    await callback.message.answer(
        TEXTS["welcome"],
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )


# =============================================================================
# ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ (ТОЛЬКО В НУЖНЫХ СОСТОЯНИЯХ!)
# =============================================================================

@router.message(ContactStates.waiting_phone)
async def process_phone_input(message: Message, state: FSMContext):
    """
    Обработка ввода телефона.
    ВАЖНО: Срабатывает ТОЛЬКО в состоянии waiting_phone!
    """
    user_id = message.from_user.id
    phone_input = message.text.strip()
    
    logger.info(f"User {user_id} entered phone: {phone_input}")
    
    # Валидируем телефон
    result: ValidationResult = validate_phone(phone_input)
    
    if not result.is_valid:
        # Ошибка валидации - просим ввести снова
        logger.info(f"Phone validation failed for user {user_id}: {result.error}")
        
        await message.answer(
            f"❌ {result.error}\n\n"
            f"{TEXTS['contact_phone_format_hint']}",
            parse_mode="HTML",
            reply_markup=get_skip_phone_keyboard()
        )
        return
    
    # Телефон валиден
    normalized_phone = result.normalized_value
    logger.info(f"Phone validated for user {user_id}: {normalized_phone}")
    
    # Сохраняем в FSM
    await state.update_data(phone=normalized_phone)
    
    # Переходим к email
    await state.set_state(ContactStates.waiting_email)
    
    await message.answer(
        f"✅ Телефон принят: <code>{normalized_phone}</code>\n\n"
        f"{TEXTS['contact_email_request']}",
        parse_mode="HTML",
        reply_markup=get_skip_email_keyboard()
    )


@router.message(ContactStates.waiting_email)
async def process_email_input(message: Message, state: FSMContext, db: Database):
    """
    Обработка ввода email.
    ВАЖНО: Срабатывает ТОЛЬКО в состоянии waiting_email!
    """
    user_id = message.from_user.id
    email_input = message.text.strip()
    
    logger.info(f"User {user_id} entered email: {email_input}")
    
    # Валидируем email
    result: ValidationResult = validate_email(email_input)
    
    if not result.is_valid:
        # Ошибка валидации - просим ввести снова
        logger.info(f"Email validation failed for user {user_id}: {result.error}")
        
        await message.answer(
            f"❌ {result.error}\n\n"
            f"{TEXTS['contact_email_format_hint']}",
            parse_mode="HTML",
            reply_markup=get_skip_email_keyboard()
        )
        return
    
    # Email валиден
    normalized_email = result.normalized_value
    logger.info(f"Email validated for user {user_id}: {normalized_email}")
    
    # Сохраняем в FSM
    await state.update_data(email=normalized_email)
    
    # Показываем подтверждение
    await show_confirmation(message, state, db, user_id)


# =============================================================================
# ПОКАЗ ПОДТВЕРЖДЕНИЯ
# =============================================================================

async def show_confirmation(message: Message, state: FSMContext, db: Database, user_id: int):
    """Показывает экран подтверждения контактов."""
    data = await state.get_data()
    phone = data.get("phone")
    email = data.get("email")
    
    # Формируем текст
    phone_display = f"<code>{phone}</code>" if phone else "не указан"
    email_display = f"<code>{email}</code>" if email else "не указан"
    
    await state.set_state(ContactStates.confirming)
    
    await message.answer(
        f"📋 <b>Проверьте ваши данные:</b>\n\n"
        f"📞 Телефон: {phone_display}\n"
        f"📧 Email: {email_display}\n\n"
        "Всё верно?",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard()
    )
