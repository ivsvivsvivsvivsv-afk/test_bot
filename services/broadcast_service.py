"""
Broadcast service — safe mass messaging.

Rate limit: 20 msg/sec (asyncio.sleep(0.05)).
TelegramRetryAfter → await sleep(retry_after).
TelegramForbiddenError → UPDATE is_blocked = TRUE in finally.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import asyncpg
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

logger = logging.getLogger(__name__)

BROADCAST_DELAY = 0.05


def _segment_filter(segment_id: str) -> tuple[str, list[Any]]:
    sid = (segment_id or "all").strip()
    base = "is_blocked = FALSE"
    if sid == "all":
        return base, []
    if sid == "visitors":
        return (
            f"{base} AND EXISTS (SELECT 1 FROM events e WHERE e.user_id = users.user_id AND e.event_type = 'bot_start')",
            [],
        )
    if sid == "quest_started":
        return (
            f"{base} AND EXISTS (SELECT 1 FROM events e WHERE e.user_id = users.user_id AND e.event_type = 'quest_start')",
            [],
        )
    if sid == "quest_in_progress":
        return f"{base} AND quest_completed = FALSE AND quest_state NOT IN ('start', 'completed')", []
    if sid == "quest_completed":
        return f"{base} AND quest_completed = TRUE", []
    if sid == "workshop_registered":
        return f"{base} AND workshop_registered = TRUE", []
    if sid == "not_workshop":
        return f"{base} AND quest_completed = TRUE AND workshop_registered = FALSE", []
    if sid == "arena_only":
        return f"{base} AND arena_registered = TRUE AND quest_completed = FALSE", []
    if sid == "has_phone":
        return f"{base} AND phone IS NOT NULL", []
    if sid == "paid":
        return (
            f"{base} AND EXISTS (SELECT 1 FROM payments p WHERE p.user_id = users.user_id AND p.status = 'succeeded')",
            [],
        )
    if sid == "followup_day1":
        return f"{base} AND followup_stage = 0 AND quest_completed = TRUE AND workshop_registered = FALSE", []
    if sid == "followup_day2_5":
        return f"{base} AND followup_stage BETWEEN 1 AND 4 AND quest_completed = TRUE AND workshop_registered = FALSE", []

    if sid.startswith("by_class:"):
        return f"{base} AND player_class = $1", [sid.split(":", 1)[1]]
    if sid.startswith("by_weapon:"):
        return f"{base} AND weapon = $1", [sid.split(":", 1)[1]]
    if sid.startswith("by_utm:"):
        return f"{base} AND utm_source = $1", [sid.split(":", 1)[1]]
    if sid.startswith("registered_after:"):
        raw = sid.split(":", 1)[1]
        dt = datetime.fromisoformat(raw)
        return f"{base} AND created_at >= $1", [dt]

    raise ValueError(f"Unknown segment_id: {sid}")


async def _load_segment_user_ids(pool: asyncpg.Pool, segment_id: str) -> list[int]:
    where_sql, params = _segment_filter(segment_id)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT user_id FROM users WHERE {where_sql} ORDER BY user_id",
            *params,
        )
    return [int(r["user_id"]) for r in rows]


async def count_segment_users(pool: asyncpg.Pool, segment_id: str) -> int:
    where_sql, params = _segment_filter(segment_id)
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*)::int FROM users WHERE {where_sql}",
            *params,
        )
    return int(total or 0)


async def _broadcast_to_user_ids(
    bot: Bot,
    pool: asyncpg.Pool,
    user_ids: list[int],
    text: str,
    **send_kwargs,
) -> dict:
    sent = 0
    failed = 0
    blocked_count = 0
    total = len(user_ids)

    for idx, user_id in enumerate(user_ids):
        blocked = False
        try:
            await bot.send_message(user_id, text, **send_kwargs)
            sent += 1
        except TelegramRetryAfter as e:
            logger.warning("Broadcast rate limited at %d/%d, sleeping %ss", idx, total, e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(user_id, text, **send_kwargs)
                sent += 1
            except TelegramForbiddenError:
                blocked = True
                failed += 1
            except Exception:
                failed += 1
                logger.warning("Broadcast retry failed for user %s", user_id)
        except TelegramForbiddenError:
            blocked = True
            failed += 1
        except Exception:
            failed += 1
            logger.warning("Broadcast send failed for user %s", user_id)
        finally:
            if blocked:
                blocked_count += 1
                try:
                    await pool.execute(
                        "UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                        user_id,
                    )
                except Exception:
                    logger.exception("Failed to set is_blocked for user %s", user_id)

        await asyncio.sleep(BROADCAST_DELAY)

    logger.info(
        "Broadcast finished: sent=%d failed=%d blocked=%d total=%d",
        sent, failed, blocked_count, total,
    )
    return {"sent": sent, "failed": failed, "blocked": blocked_count, "total": total}


async def broadcast(
    bot: Bot,
    pool: asyncpg.Pool,
    text: str,
    **send_kwargs,
) -> dict:
    """
    Send message to all non-blocked users.
    Returns {"sent": N, "failed": M, "blocked": B}.
    """
    user_ids = await _load_segment_user_ids(pool, "all")
    result = await _broadcast_to_user_ids(
        bot=bot,
        pool=pool,
        user_ids=user_ids,
        text=text,
        **send_kwargs,
    )
    return {
        "sent": result["sent"],
        "failed": result["failed"],
        "blocked": result["blocked"],
    }


async def broadcast_segment(
    bot: Bot,
    pool: asyncpg.Pool,
    text: str,
    segment_id: str = "all",
    **send_kwargs,
) -> dict:
    user_ids = await _load_segment_user_ids(pool, segment_id)
    result = await _broadcast_to_user_ids(
        bot=bot,
        pool=pool,
        user_ids=user_ids,
        text=text,
        **send_kwargs,
    )
    return {
        "segment_id": segment_id,
        "sent": result["sent"],
        "failed": result["failed"],
        "blocked": result["blocked"],
    }


async def process_due_scheduled_broadcasts(
    bot: Bot,
    pool: asyncpg.Pool,
    max_jobs: int = 5,
) -> int:
    processed = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT id, text, segment_id
                FROM scheduled_broadcasts
                WHERE status = 'pending'
                  AND scheduled_at IS NOT NULL
                  AND scheduled_at <= NOW()
                ORDER BY scheduled_at ASC
                LIMIT $1
                FOR UPDATE SKIP LOCKED
                """,
                max_jobs,
            )
            ids = [r["id"] for r in rows]
            if ids:
                await conn.execute(
                    "UPDATE scheduled_broadcasts SET status = 'running' WHERE id = ANY($1::int[])",
                    ids,
                )

    for row in rows:
        bid = int(row["id"])
        try:
            result = await broadcast_segment(
                bot=bot,
                pool=pool,
                text=row["text"],
                segment_id=row["segment_id"] or "all",
            )
            await pool.execute(
                """
                UPDATE scheduled_broadcasts
                SET status = 'sent',
                    sent_at = NOW(),
                    result_sent = $2,
                    result_failed = $3
                WHERE id = $1
                """,
                bid,
                int(result["sent"]),
                int(result["failed"]),
            )
            processed += 1
        except Exception:
            logger.exception("Scheduled broadcast failed id=%s", bid)
            await pool.execute(
                "UPDATE scheduled_broadcasts SET status = 'failed', sent_at = NOW() WHERE id = $1",
                bid,
            )
    return processed
