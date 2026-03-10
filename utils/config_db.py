from __future__ import annotations

import time
from typing import Any, Dict, Optional

import asyncpg

DEFAULT_CONFIG: Dict[str, str] = {
    "upsell_total_slots": "10",
    "upsell_price": "5000",
    "upsell_enabled": "true",
    "followup_enabled": "true",
    "bot_active": "true",
}

_cache: Optional[Dict[str, Any]] = None
_cache_ts: float = 0.0
_CACHE_TTL: float = 30.0


async def get_config(pool: asyncpg.Pool, *, force: bool = False) -> Dict[str, Any]:
    """
    Read runtime configuration from PostgreSQL config table.
    Caches for 30 seconds to avoid hitting DB on every upsell/payment check.
    Under 10K CCU, get_config is called from: upsell show, payment create,
    payment webhook, admin /stats, admin /slots — easily 100+/sec without cache.
    """
    global _cache, _cache_ts
    now = time.monotonic()

    if not force and _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache

    rows = await pool.fetch("SELECT key, value FROM config")
    config: Dict[str, Any] = {row["key"]: row["value"] for row in rows}

    for key, default_value in DEFAULT_CONFIG.items():
        config.setdefault(key, default_value)

    _cache = config
    _cache_ts = now
    return config


def invalidate_config_cache() -> None:
    """Force next get_config() to re-read from DB."""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0
