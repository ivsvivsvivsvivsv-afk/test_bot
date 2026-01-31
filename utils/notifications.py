"""
Уведомления администраторам.

Отправка уведомлений о новых пользователях, контактах и событиях.
"""

import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import settings

logger = logging.getLogger(__name__)


async def notify_admins(
    bot: Bot,
    message: str,
    parse_mode: str = "HTML"
) -> int:
    """
    Отправляет уведомление всем администраторам.
    
    Args:
        bot: Экземпляр бота
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML/Markdown)
    
    Returns:
        Количество успешно отправленных уведомлений
    """
    success_count = 0
    
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=parse_mode
            )
            success_count += 1
            logger.debug(f"Notification sent to admin {admin_id}")
        except TelegramForbiddenError:
            logger.warning(f"Admin {admin_id} has blocked the bot")
        except TelegramBadRequest as e:
            logger.error(f"Failed to send to admin {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending to admin {admin_id}: {e}")
    
    return success_count


async def notify_new_user(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    source: Optional[str] = None
) -> None:
    """
    Уведомление о новом пользователе.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Username пользователя
        full_name: Полное имя
        source: Источник (utm_source)
    """
    username_display = f"@{username}" if username else "нет username"
    source_display = source if source else "не указан"
    
    message = (
        "👤 <b>Новый пользователь</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {username_display}\n"
        f"📍 Источник: {source_display}"
    )
    
    await notify_admins(bot, message)


async def notify_new_contact(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    phone: Optional[str],
    email: Optional[str]
) -> None:
    """
    Уведомление о новом контакте.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Username
        full_name: Полное имя
        phone: Номер телефона
        email: Email
    """
    username_display = f"@{username}" if username else "нет"
    phone_display = phone if phone else "не указан"
    email_display = email if email else "не указан"
    
    message = (
        "📱 <b>Новый контакт</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {username_display}\n"
        f"📞 Телефон: <code>{phone_display}</code>\n"
        f"📧 Email: <code>{email_display}</code>"
    )
    
    await notify_admins(bot, message)


async def notify_quest_completed(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    result: str,
    score: int
) -> None:
    """
    Уведомление о завершении квеста.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Username
        full_name: Полное имя
        result: Результат (специализация)
        score: Набранные очки
    """
    username_display = f"@{username}" if username else "нет"
    
    message = (
        "🎮 <b>Квест пройден</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {username_display}\n"
        f"🏆 Результат: {result}\n"
        f"⭐ Очки: {score}"
    )
    
    await notify_admins(bot, message)


async def notify_arena_completed(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    specialization: str,
    tasks_completed: int,
    total_tasks: int
) -> None:
    """
    Уведомление о завершении арены.
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Username
        full_name: Полное имя
        specialization: Выбранная специализация
        tasks_completed: Выполнено заданий
        total_tasks: Всего заданий
    """
    username_display = f"@{username}" if username else "нет"
    
    message = (
        "⚔️ <b>Арена пройдена</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {username_display}\n"
        f"🎯 Специализация: {specialization}\n"
        f"✅ Задания: {tasks_completed}/{total_tasks}"
    )
    
    await notify_admins(bot, message)


async def notify_error(
    bot: Bot,
    error_type: str,
    error_message: str,
    user_id: Optional[int] = None
) -> None:
    """
    Уведомление об ошибке.
    
    Args:
        bot: Экземпляр бота
        error_type: Тип ошибки
        error_message: Сообщение об ошибке
        user_id: ID пользователя (если связано с пользователем)
    """
    user_info = f"\n🆔 User ID: <code>{user_id}</code>" if user_id else ""
    
    message = (
        f"⚠️ <b>Ошибка: {error_type}</b>\n"
        f"{user_info}\n"
        f"📝 Описание: <code>{error_message[:500]}</code>"
    )
    
    await notify_admins(bot, message)
