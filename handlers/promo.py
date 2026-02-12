"""
Промо-акция после регистрации.

HIGHLOAD АРХИТЕКТУРА:
- Redis distributed locks (работает с несколькими инстансами!)
- Атомарные операции через PostgreSQL
- YooKassa webhook обработка

Для 100K+ пользователей!
"""

import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from config import settings
from database import DatabaseInterface
from utils.notifications import notify_admins

logger = logging.getLogger(__name__)
router = Router(name="promo")


# =============================================================================
# REDIS DISTRIBUTED LOCK
# =============================================================================

class RedisLock:
    """
    Distributed lock через Redis.
    Работает корректно при нескольких инстансах!
    """
    
    def __init__(self, redis_client, lock_name: str, timeout: int = 10):
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self._locked = False
    
    async def __aenter__(self):
        if self.redis:
            # SET NX with expiration - атомарная операция
            self._locked = await self.redis.set(
                self.lock_name, 
                "1", 
                nx=True,  # Only set if not exists
                ex=self.timeout
            )
            if not self._locked:
                # Lock уже занят другим инстансом
                raise LockAcquireError("Could not acquire lock")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis and self._locked:
            await self.redis.delete(self.lock_name)


class LockAcquireError(Exception):
    """Не удалось получить lock."""
    pass


# Глобальный Redis клиент (инициализируется в bot.py)
_redis_client = None


def set_redis_client(client):
    """Устанавливается из bot.py при инициализации."""
    global _redis_client
    _redis_client = client


async def get_distributed_lock(name: str, timeout: int = 10) -> RedisLock:
    """Получить distributed lock."""
    return RedisLock(_redis_client, name, timeout)


# =============================================================================
# PROMO TEXTS
# =============================================================================

PROMO_TEXT = """
🎁 <b>ЭКСКЛЮЗИВНОЕ ПРЕДЛОЖЕНИЕ</b>

Вы только что завершили регистрацию на открытый урок НЕЙРО-ЮНИТ!

Специально для первых участников — <b>уникальная возможность</b>:

💼 <b>Персональный разбор вашего бизнеса</b>
— Анализ текущей ситуации
— Точки роста с помощью ИИ
— Готовый план внедрения

⏰ <b>Осталось мест: {slots}</b>

💰 <b>Цена: 5 000 ₽</b> (вместо 15 000 ₽)

⚡️ Предложение действует только для участников открытого урока!
"""

PROMO_SUCCESS_TEXT = """
✅ <b>Оплата прошла успешно!</b>

Спасибо за доверие! 

В течение 24 часов с вами свяжется наш менеджер для назначения времени консультации.

До встречи! 🚀
"""

PROMO_SLOTS_ENDED_TEXT = """
😔 К сожалению, все места на персональный разбор уже заняты.

Но не расстраивайтесь — впереди открытый урок, где вы узнаете много полезного!

До встречи! 👋
"""


# =============================================================================
# PROMO FUNCTIONS
# =============================================================================

async def send_promo_offer(bot: Bot, db: DatabaseInterface, user_id: int, chat_id: int) -> None:
    """
    Отправить промо-предложение после регистрации.
    
    Вызывается из contacts.py после подтверждения контактов.
    """
    try:
        # Проверяем, не отправляли ли уже
        existing_status = await db.get_user_promo_status(user_id)
        if existing_status:
            logger.info(f"Promo already sent to user {user_id}, status: {existing_status}")
            return
        
        # Проверяем доступные слоты
        slots = await db.get_promo_slots()
        if slots <= 0:
            logger.info(f"No promo slots left, skipping for user {user_id}")
            return
        
        # Формируем сообщение
        text = PROMO_TEXT.format(slots=slots)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Оплатить 5 000 ₽",
                callback_data="promo_pay"
            )]
        ])
        
        # Отправляем
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard
        )
        
        # Сохраняем в БД
        await db.save_promo_message(user_id, chat_id, msg.message_id, status='sent')
        
        logger.info(f"Promo offer sent to user {user_id}, message_id: {msg.message_id}")
        
    except Exception as e:
        logger.exception(f"Error sending promo to user {user_id}: {e}")


@router.callback_query(F.data == "promo_pay")
async def cb_promo_pay(callback: CallbackQuery, db: DatabaseInterface):
    """
    Обработка нажатия кнопки оплаты.
    
    Использует distributed lock для атомарности при множестве инстансов!
    """
    user_id = callback.from_user.id
    
    try:
        # Проверяем, не оплачено ли уже
        status = await db.get_user_promo_status(user_id)
        if status == 'paid':
            await callback.answer("Вы уже оплатили!", show_alert=True)
            return
        
        # Пытаемся получить distributed lock
        try:
            lock = await get_distributed_lock(f"promo_payment:{user_id}", timeout=30)
            async with lock:
                # Внутри lock — проверяем слоты ещё раз (double-check)
                slots = await db.get_promo_slots()
                
                if slots <= 0:
                    # Слоты закончились
                    await callback.message.edit_text(
                        PROMO_SLOTS_ENDED_TEXT,
                        reply_markup=None
                    )
                    await db.update_promo_status(user_id, 'slots_ended')
                    await callback.answer()
                    return
                
                # Создаём платёж в YooKassa
                if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
                    await callback.answer(
                        "Платежи временно недоступны. Попробуйте позже.",
                        show_alert=True
                    )
                    logger.error("YooKassa not configured!")
                    return
                
                payment_url = await create_yookassa_payment(user_id)
                
                if payment_url:
                    # Обновляем сообщение с кнопкой оплаты
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="💳 Перейти к оплате",
                            url=payment_url
                        )],
                        [InlineKeyboardButton(
                            text="✅ Я оплатил",
                            callback_data="promo_check_payment"
                        )]
                    ])
                    
                    await callback.message.edit_reply_markup(reply_markup=keyboard)
                    await callback.answer("Переходите к оплате!", show_alert=False)
                else:
                    await callback.answer(
                        "Ошибка создания платежа. Попробуйте позже.",
                        show_alert=True
                    )
                    
        except LockAcquireError:
            # Другой инстанс уже обрабатывает
            await callback.answer("Подождите, обрабатывается...", show_alert=False)
            
    except Exception as e:
        logger.exception(f"Error in promo payment for user {user_id}: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


async def create_yookassa_payment(user_id: int) -> Optional[str]:
    """Создать платёж в YooKassa."""
    try:
        from yookassa import Configuration, Payment
        import uuid
        
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key
        
        payment = Payment.create({
            "amount": {
                "value": "5000.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.yookassa_return_url
            },
            "capture": True,
            "description": f"НЕЙРО-ЮНИТ: Персональный разбор бизнеса",
            "metadata": {
                "user_id": str(user_id)
            }
        }, uuid.uuid4())
        
        logger.info(f"YooKassa payment created: {payment.id} for user {user_id}")
        
        return payment.confirmation.confirmation_url
        
    except Exception as e:
        logger.exception(f"YooKassa payment creation error: {e}")
        return None


@router.callback_query(F.data == "promo_check_payment")
async def cb_check_payment(callback: CallbackQuery, db: DatabaseInterface):
    """Пользователь нажал 'Я оплатил'."""
    user_id = callback.from_user.id
    
    status = await db.get_user_promo_status(user_id)
    
    if status == 'paid':
        await callback.message.edit_text(
            PROMO_SUCCESS_TEXT,
            reply_markup=None
        )
        await callback.answer("Оплата подтверждена!", show_alert=False)
    else:
        await callback.answer(
            "Платёж ещё не подтверждён. Подождите 1-2 минуты или обратитесь в поддержку.",
            show_alert=True
        )


# =============================================================================
# PAYMENT CONFIRMATION (вызывается из webhook)
# =============================================================================

async def confirm_promo_payment(bot: Bot, db: DatabaseInterface, user_id: int, payment_id: str) -> None:
    """
    Подтверждение оплаты.
    
    Вызывается из bot.py при получении webhook от YooKassa.
    """
    try:
        # Проверяем текущий статус
        status = await db.get_user_promo_status(user_id)
        
        if status == 'paid':
            logger.info(f"Payment already confirmed for user {user_id}")
            return
        
        # Обновляем статус
        await db.update_promo_status(user_id, 'paid', payment_id)
        
        # Уменьшаем счётчик слотов (атомарно в PostgreSQL)
        remaining = await db.decrement_promo_slots()
        
        logger.info(f"Payment confirmed for user {user_id}, remaining slots: {remaining}")
        
        # Уведомляем админов
        admin_text = (
            f"💰 <b>Новая оплата промо!</b>\n\n"
            f"User ID: {user_id}\n"
            f"Payment ID: {payment_id}\n"
            f"Осталось мест: {remaining}"
        )
        await notify_admins(bot, admin_text)
        
        # Отправляем пользователю подтверждение
        try:
            await bot.send_message(
                chat_id=user_id,
                text=PROMO_SUCCESS_TEXT
            )
        except Exception as e:
            logger.warning(f"Could not send confirmation to user {user_id}: {e}")
        
        # Если слоты закончились — удаляем все sent сообщения
        if remaining <= 0:
            await cleanup_promo_messages(bot, db)
            
    except Exception as e:
        logger.exception(f"Error confirming payment for user {user_id}: {e}")


async def cleanup_promo_messages(bot: Bot, db: DatabaseInterface) -> None:
    """
    Удалить все неоплаченные промо-сообщения.
    
    Вызывается когда заканчиваются слоты.
    """
    try:
        messages = await db.get_all_sent_promo_messages()
        
        logger.info(f"Cleaning up {len(messages)} promo messages")
        
        for msg in messages:
            try:
                await bot.delete_message(
                    chat_id=msg['chat_id'],
                    message_id=msg['message_id']
                )
            except TelegramBadRequest as e:
                # Сообщение уже удалено или недоступно
                logger.debug(f"Could not delete message: {e}")
            except Exception as e:
                logger.warning(f"Error deleting message: {e}")
            
            # Отмечаем как удалённое
            await db.mark_promo_deleted(msg['user_id'])
        
        logger.info("Promo cleanup completed")
        
    except Exception as e:
        logger.exception(f"Error in promo cleanup: {e}")
