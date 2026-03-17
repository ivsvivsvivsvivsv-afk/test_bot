"""
Runtime alerts for critical infrastructure failures.

Uses throttling to avoid alert storms.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aiogram import Bot

from utils.notifications import notify_admins

logger = logging.getLogger(__name__)

_local_alert_ts: dict[str, float] = {}


async def send_runtime_alert(
    bot: Bot | None,
    *,
    redis_conn: Any = None,
    key: str,
    message: str,
    min_interval_sec: int = 900,
) -> bool:
    """
    Send throttled alert to admins.

    Returns True when alert was sent, False when skipped by throttle or bot unavailable.
    """
    if bot is None:
        return False

    now = time.monotonic()
    local_prev = _local_alert_ts.get(key, 0.0)
    if now - local_prev < min_interval_sec:
        return False

    if redis_conn is not None:
        try:
            redis_key = f"alert:runtime:{key}"
            ok = await redis_conn.set(redis_key, "1", ex=min_interval_sec, nx=True)
            if not ok:
                return False
        except Exception:
            logger.exception("Runtime alert Redis throttle failed for key=%s", key)

    try:
        await notify_admins(bot, message)
        _local_alert_ts[key] = now
        return True
    except Exception:
        logger.exception("Failed to send runtime alert key=%s", key)
        return False
