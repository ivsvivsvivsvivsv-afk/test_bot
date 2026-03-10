"""
PostgreSQL pool helper for asyncpg.

Single shared pool per process. Designed for Gunicorn workers where each worker
creates its own pool with capped size.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import asyncpg

from config import DB_DSN, DB_POOL_MAX, DB_POOL_MIN

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def create_pool(
    dsn: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    retries: int = 3,
) -> asyncpg.Pool:
    """
    Create asyncpg pool with retry + startup health check.
    """
    global _pool
    if _pool is not None:
        return _pool

    _dsn = dsn or DB_DSN
    _min = min_size if min_size is not None else DB_POOL_MIN
    _max = max_size if max_size is not None else DB_POOL_MAX

    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        candidate: Optional[asyncpg.Pool] = None
        try:
            candidate = await asyncpg.create_pool(
                dsn=_dsn,
                min_size=_min,
                max_size=_max,
                command_timeout=10,
            )
            async with candidate.acquire() as conn:
                await conn.fetchval("SELECT 1")
            _pool = candidate
            logger.info(
                "PostgreSQL pool created: min=%d max=%d attempt=%d/%d",
                _min,
                _max,
                attempt,
                retries,
            )
            return _pool
        except Exception as exc:
            last_error = exc
            if candidate is not None:
                try:
                    await candidate.close()
                except Exception:
                    pass
            logger.warning(
                "PostgreSQL connection attempt %d/%d failed: %s",
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                await asyncio.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Could not create PostgreSQL pool after {retries} attempts") from last_error


async def close_pool(pool: Optional[asyncpg.Pool] = None) -> None:
    """
    Gracefully close pool created by create_pool().
    """
    global _pool
    target_pool = pool or _pool
    if target_pool is not None:
        await target_pool.close()
        if target_pool is _pool:
            _pool = None
        logger.info("PostgreSQL pool closed")


def get_pool() -> asyncpg.Pool:
    """
    Return process-wide pool.
    """
    if _pool is None:
        raise RuntimeError("DB pool is not initialized. Call create_pool() first.")
    return _pool


async def init_schema(pool: asyncpg.Pool, schema_path: str = "schema.sql") -> None:
    """
    Apply schema SQL from file.
    """
    sql = Path(schema_path).read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("Schema applied from %s", schema_path)
