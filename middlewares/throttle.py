"""
Throttle middleware — max 3 messages per second per user.

Uses Redis to track last activity. Prevents spam from single user.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)

MIN_INTERVAL = 0.34  # ~3 msg/sec


class ThrottleMiddleware(BaseMiddleware):
    """Drops events from user if they exceed rate limit."""

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

        if not user or not redis_conn:
            return await handler(event, data)

        key = f"throttle:{user.id}"
        now = time.time()
        try:
            last_raw = await redis_conn.get(key)
            if last_raw:
                last = float(last_raw)
                if (now - last) < MIN_INTERVAL:
                    logger.debug("Throttle: user %s rate limited", user.id)
                    return

            await redis_conn.set(key, str(now), ex=60)
        except Exception:
            logger.exception("Throttle: Redis error for user %s", user.id)

        return await handler(event, data)
