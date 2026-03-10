"""
Admin notifications via Telegram.

Sends structured messages to every admin in ADMIN_IDS.
Silently skips admins who blocked the bot (TelegramForbiddenError).
"""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, message: str, parse_mode: str = "HTML") -> int:
    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=message, parse_mode=parse_mode)
            sent += 1
        except TelegramForbiddenError:
            logger.warning("Admin %s blocked the bot", admin_id)
        except TelegramBadRequest as exc:
            logger.error("Bad request to admin %s: %s", admin_id, exc)
        except Exception:
            logger.exception("Unexpected error sending to admin %s", admin_id)
    return sent


async def notify_new_user(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    source: Optional[str] = None,
) -> None:
    un = f"@{username}" if username else "—"
    src = source or "—"
    await notify_admins(
        bot,
        f"👤 <b>Новый пользователь</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {un}\n"
        f"📍 Источник: {src}",
    )


async def notify_quest_completed(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    score: int,
    player_class: str,
    weapon: str,
) -> None:
    un = f"@{username}" if username else "—"
    await notify_admins(
        bot,
        f"🎮 <b>Квест пройден</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Username: {un}\n"
        f"🎭 Класс: {player_class}\n"
        f"⚔️ Оружие: {weapon}\n"
        f"⭐ Очки: {score}/3",
    )


async def notify_new_contact(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    phone: Optional[str],
) -> None:
    un = f"@{username}" if username else "—"
    await notify_admins(
        bot,
        f"📱 <b>Новый контакт</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Telegram: {un}\n"
        f"📞 Телефон: <code>{phone or '—'}</code>",
    )


EXPERIENCE_LABELS = {
    "beginner": "Только начинаю",
    "intermediate": "Несколько месяцев",
    "advanced": "Больше года, ежедневно",
}
TOOLS_LABELS = {
    "chat": "ChatGPT / Claude",
    "image": "Midjourney / DALL-E / SD",
    "dev": "API, автоматизации",
    "all": "Всё вышеперечисленное",
}
GOAL_LABELS = {
    "bot": "Чат-бота или ассистента",
    "analytics": "Аналитический инструмент",
    "content": "Генератор контента",
    "custom": "Свой проект",
}


def _score_arena_lead(q1: str, q2: str, q3: str) -> str:
    if q1 == "advanced" and q2 in ("dev", "all"):
        return "🔥 ГОРЯЧИЙ"
    if q1 == "intermediate" or q2 in ("dev", "all") or q3 in ("bot", "analytics"):
        return "🟡 ТЁПЛЫЙ"
    return "🟢 ХОЛОДНЫЙ"


async def notify_arena_lead(
    bot: Bot,
    user_id: int,
    username: Optional[str],
    full_name: str,
    phone: Optional[str],
    q1: str,
    q2: str,
    q3: str,
) -> None:
    un = f"@{username}" if username else "—"
    scoring = _score_arena_lead(q1, q2, q3)
    await notify_admins(
        bot,
        f"⚔️ <b>НОВЫЙ ЛИД С АРЕНЫ</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Имя: {full_name}\n"
        f"🔗 Telegram: {un}\n\n"
        f"📊 <b>Квалификация:</b>\n"
        f"  Опыт: {EXPERIENCE_LABELS.get(q1, q1)}\n"
        f"  Инструменты: {TOOLS_LABELS.get(q2, q2)}\n"
        f"  Цель: {GOAL_LABELS.get(q3, q3)}\n\n"
        f"📱 Телефон: <code>{phone or '—'}</code>\n\n"
        f"🎯 Скоринг: {scoring}",
    )


async def notify_error(
    bot: Bot,
    error_type: str,
    error_message: str,
    user_id: Optional[int] = None,
) -> None:
    user_info = f"\n🆔 User ID: <code>{user_id}</code>" if user_id else ""
    await notify_admins(
        bot,
        f"⚠️ <b>Ошибка: {error_type}</b>{user_info}\n"
        f"📝 <code>{error_message[:500]}</code>",
    )
