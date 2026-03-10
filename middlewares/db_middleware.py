from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

import asyncpg
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis


class DBMiddleware(BaseMiddleware):
    """
    Inject asyncpg pool and Redis connection into handler data.
    """

    def __init__(self, pool: asyncpg.Pool, redis_conn: Redis):
        self.pool = pool
        self.redis_conn = redis_conn

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["pool"] = self.pool
        data["redis_conn"] = self.redis_conn
        return await handler(event, data)
