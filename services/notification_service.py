"""
Notification service — structured admin alerts.

Formats event_type + data and sends to all admins via utils.notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from config import ADMIN_IDS
from utils.notifications import notify_admins

logger = logging.getLogger(__name__)


def _format_event(event_type: str, data: Dict[str, Any]) -> str:
    lines = [f"🔔 <b>{event_type}</b>", ""]
    for k, v in data.items():
        if v is not None and v != "":
            lines.append(f"  {k}: <code>{v}</code>")
    return "\n".join(lines)


async def notify_admins_event(
    bot: Bot,
    event_type: str,
    data: Dict[str, Any],
) -> int:
    """
    Send structured notification to all admins.
    Silently skips blocked admins.
    Returns count of admins notified.
    """
    text = _format_event(event_type, data)
    return await notify_admins(bot, text)


async def notify_payment_success(
    bot: Bot,
    user_id: int,
    amount: str,
    description: str = "",
) -> int:
    return await notify_admins_event(
        bot,
        "payment_success",
        {"user_id": user_id, "amount": amount, "description": description},
    )


async def notify_auto_refund(
    bot: Bot,
    user_id: int,
    payment_id: str,
    reason: str,
) -> int:
    return await notify_admins_event(
        bot,
        "auto_refund",
        {"user_id": user_id, "payment_id": payment_id, "reason": reason},
    )
