"""
Activity tracking middleware — Redis SETEX with TTL.

Stores activity:{user_id} in Redis so worker can detect idle users.
TTL = FOLLOWUP_IDLE_MINUTES * 60. Do NOT use PostgreSQL for this —
10K users × 1 UPDATE/min = MVCC bloat.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from config import FOLLOWUP_IDLE_MINUTES

logger = logging.getLogger(__name__)

ACTIVITY_TTL = FOLLOWUP_IDLE_MINUTES * 60


class ActivityMiddleware(BaseMiddleware):
    """Sets activity:{user_id} in Redis on every user update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        redis_conn = data.get("redis_conn")
        user = None
        if hasattr(event, "from_user") and event.from_user:
            user = event.from_user
        elif hasattr(event, "message") and event.message and event.message.from_user:
            user = event.message.from_user

        if user and redis_conn:
            try:
                await redis_conn.setex(f"activity:{user.id}", ACTIVITY_TTL, "1")
            except Exception:
                logger.exception("ActivityMiddleware: failed to set activity for user %s", user.id)

        return await handler(event, data)
