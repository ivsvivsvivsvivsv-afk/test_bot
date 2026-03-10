"""
Quest business-logic layer.

All DB writes and reads for the quest flow live here so that handlers stay thin.
Every public function accepts an asyncpg.Pool (not a single connection) — the pool
is cheap to pass around and lets the service acquire/release connections itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


# ── User helpers ────────────────────────────────────────────


async def get_or_create_user(
    pool: asyncpg.Pool,
    *,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return existing user row or INSERT a new one.
    Uses ON CONFLICT so it's safe under concurrent /start.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (user_id, username, first_name, utm_source)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
                SET username   = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    is_blocked = FALSE
            RETURNING *
            """,
            user_id,
            username,
            first_name,
            source,
        )
    return dict(row)


async def get_user(pool: asyncpg.Pool, user_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(row) if row else None


# ── Quest state persistence (PG backup) ────────────────────


_ALLOWED_UPDATE_COLUMNS = frozenset({
    "quest_state", "quest_completed", "player_class", "weapon",
    "score", "round_number", "current_statement_hash", "current_is_truth",
    "phone", "email", "workshop_registered", "arena_registered",
    "followup_stage", "followup_completed", "is_blocked", "upsell_shown",
    "quest_completed_at",
})


async def update_quest_state(
    pool: asyncpg.Pool,
    user_id: int,
    quest_state: str,
    **extra_fields: Any,
) -> None:
    """
    Write quest_state + any extra columns atomically.
    ``extra_fields`` keys must match column names in the users table.
    """
    sets = ["quest_state = $2"]
    vals: list[Any] = [user_id, quest_state]
    idx = 3
    for col, val in extra_fields.items():
        if col not in _ALLOWED_UPDATE_COLUMNS:
            raise ValueError(f"Column '{col}' is not in the allowed update list")
        sets.append(f"{col} = ${idx}")
        vals.append(val)
        idx += 1

    sql = f"UPDATE users SET {', '.join(sets)} WHERE user_id = $1"
    async with pool.acquire() as conn:
        await conn.execute(sql, *vals)
    logger.debug("quest_state=%s for user %s", quest_state, user_id)


async def save_class(pool: asyncpg.Pool, user_id: int, player_class: str) -> None:
    await update_quest_state(
        pool, user_id, "class_selected", player_class=player_class
    )


async def save_weapon(pool: asyncpg.Pool, user_id: int, weapon: str) -> None:
    await update_quest_state(
        pool, user_id, "weapon_selected", weapon=weapon
    )


async def save_round_start(
    pool: asyncpg.Pool,
    user_id: int,
    round_num: int,
    statement_text: str,
    is_truth: bool,
) -> None:
    stmt_hash = hashlib.sha256(statement_text.encode()).hexdigest()
    await update_quest_state(
        pool,
        user_id,
        f"round_{round_num}",
        round_number=round_num,
        current_statement_hash=stmt_hash,
        current_is_truth=is_truth,
    )


async def save_round_result(
    pool: asyncpg.Pool,
    user_id: int,
    round_num: int,
    score: int,
) -> None:
    await update_quest_state(
        pool,
        user_id,
        f"round_{round_num}_done",
        score=score,
    )


async def complete_quest(pool: asyncpg.Pool, user_id: int, score: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET
                quest_state = 'completed',
                quest_completed = TRUE,
                score = $2,
                quest_completed_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            score,
        )
    logger.debug("quest completed for user %s, score=%d", user_id, score)


# ── Event logging ───────────────────────────────────────────


async def log_event(
    pool: asyncpg.Pool,
    user_id: int,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
) -> None:
    data_json = json.dumps(event_data or {}, ensure_ascii=False)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO events (user_id, event_type, event_data) VALUES ($1, $2, $3::jsonb)",
                user_id,
                event_type,
                data_json,
            )
    except Exception:
        logger.exception("Failed to log event %s for user %s", event_type, user_id)


# ── Activity tracking (Redis) ──────────────────────────────


async def touch_activity(redis_conn, user_id: int, ttl: int | None = None) -> None:
    """SETEX activity:{user_id} with TTL. Uses FOLLOWUP_IDLE_MINUTES from config if ttl omitted."""
    from config import FOLLOWUP_IDLE_MINUTES
    _ttl = ttl if ttl is not None else FOLLOWUP_IDLE_MINUTES * 60
    try:
        await redis_conn.setex(f"activity:{user_id}", _ttl, "1")
    except Exception:
        logger.exception("Failed to touch activity for user %s", user_id)
