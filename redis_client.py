"""
Redis connection helpers.
=========================
Единственная точка подключения к Redis.
Используется для: FSM Storage, throttle, activity tracking,
slot holds (Sorted Set + Lua), file_id cache.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import redis.asyncio as aioredis

from config import REDIS_URL

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


def _mask_url(url: str) -> str:
    """redis://user:password@host:port/db → redis://user:***@host:port/db"""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


async def create_redis(
    url: Optional[str] = None,
    *,
    decode_responses: bool = True,
) -> aioredis.Redis:
    """Create and validate Redis connection."""
    global _redis
    if _redis is not None:
        return _redis

    target_url = url or REDIS_URL
    candidate = aioredis.from_url(
        target_url,
        decode_responses=decode_responses,
    )
    try:
        await candidate.ping()
    except Exception:
        await candidate.aclose()
        raise

    _redis = candidate
    logger.info("Redis connected: %s", _mask_url(target_url))
    return _redis


async def close_redis(redis_conn: Optional[aioredis.Redis] = None) -> None:
    """Close connection created by create_redis()."""
    global _redis
    target_conn = redis_conn or _redis
    if target_conn is not None:
        await target_conn.aclose()
        if target_conn is _redis:
            _redis = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Get process-wide Redis connection."""
    if _redis is None:
        raise RuntimeError("Redis is not initialized. Call create_redis() first.")
    return _redis
