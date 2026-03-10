"""
Notification rules executor (Patch 2).

Current triggers implemented:
- scheduled_once
- scheduled_recurring
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from aiogram import Bot

from services.broadcast_service import broadcast_segment

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _rule_already_sent(conn: asyncpg.Connection, rule_id: int, dedup_key: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1
            FROM events
            WHERE event_type = 'notification_rule_sent'
              AND event_data->>'rule_id' = $1
              AND event_data->>'dedup_key' = $2
            LIMIT 1
            """,
            str(rule_id),
            dedup_key,
        )
    )


async def _mark_rule_sent(
    conn: asyncpg.Connection,
    *,
    rule_id: int,
    dedup_key: str,
    result: dict[str, Any],
) -> None:
    payload = {
        "rule_id": str(rule_id),
        "dedup_key": dedup_key,
        "sent": int(result.get("sent", 0)),
        "failed": int(result.get("failed", 0)),
        "blocked": int(result.get("blocked", 0)),
    }
    await conn.execute(
        "INSERT INTO events (user_id, event_type, event_data) VALUES (0, $1, $2::jsonb)",
        "notification_rule_sent",
        json.dumps(payload, ensure_ascii=False),
    )


def _should_run_scheduled_once(trigger_cfg: dict[str, Any], now_utc: datetime) -> tuple[bool, str]:
    send_at = str(trigger_cfg.get("send_at", "")).strip()
    if not send_at:
        return False, ""
    try:
        run_dt = datetime.fromisoformat(send_at.replace("Z", "+00:00"))
    except ValueError:
        return False, ""
    if run_dt.tzinfo is None:
        run_dt = run_dt.replace(tzinfo=timezone.utc)
    run_dt = run_dt.astimezone(timezone.utc)
    dedup_key = f"once:{run_dt.isoformat()}"
    return now_utc >= run_dt, dedup_key


def _should_run_scheduled_recurring(trigger_cfg: dict[str, Any], now_utc: datetime) -> tuple[bool, str]:
    try:
        hour = int(trigger_cfg.get("hour", 0))
        minute = int(trigger_cfg.get("minute", 0))
    except (TypeError, ValueError):
        return False, ""
    days = trigger_cfg.get("days", [0, 1, 2, 3, 4, 5, 6])  # monday=0
    if not isinstance(days, list):
        return False, ""
    if now_utc.weekday() not in days:
        return False, ""
    if now_utc.hour != hour or now_utc.minute != minute:
        return False, ""
    dedup_key = f"recurring:{now_utc.strftime('%Y-%m-%d')}:{hour:02d}:{minute:02d}"
    return True, dedup_key


async def process_notification_rules(
    bot: Bot,
    pool: asyncpg.Pool,
    *,
    max_rules: int = 100,
    now_utc: datetime | None = None,
) -> int:
    now = now_utc or _utc_now()
    processed = 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text_template, segment_id, trigger_type, trigger_config
            FROM notification_rules
            WHERE enabled = TRUE
            ORDER BY id ASC
            LIMIT $1
            """,
            max_rules,
        )

    for row in rows:
        rid = int(row["id"])
        trigger_type = row["trigger_type"]
        trigger_cfg = row["trigger_config"] or {}
        should_run = False
        dedup_key = ""

        if trigger_type == "scheduled_once":
            should_run, dedup_key = _should_run_scheduled_once(trigger_cfg, now)
        elif trigger_type == "scheduled_recurring":
            should_run, dedup_key = _should_run_scheduled_recurring(trigger_cfg, now)

        if not should_run or not dedup_key:
            continue

        async with pool.acquire() as conn:
            if await _rule_already_sent(conn, rid, dedup_key):
                continue

        try:
            result = await broadcast_segment(
                bot=bot,
                pool=pool,
                text=row["text_template"],
                segment_id=row["segment_id"] or "all",
            )
            async with pool.acquire() as conn:
                await _mark_rule_sent(conn, rule_id=rid, dedup_key=dedup_key, result=result)
            processed += 1
        except Exception:
            logger.exception("Notification rule failed: id=%s", rid)

    return processed
