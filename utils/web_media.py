"""
Web media registry for static assets.

Purpose:
- keep an indexed manifest for web client media;
- provide fast in-process cached reads for handlers;
- avoid repeated disk JSON parsing under load.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MEDIA_ROOT = Path("content/web_media")
MANIFEST_PATH = Path("content/web_media_manifest.json")
MANIFEST_CACHE_TTL_SEC = 30

_manifest_cache: tuple[float, dict[str, Any]] | None = None


def _empty_manifest() -> dict[str, Any]:
    return {"version": 1, "generated_at": None, "assets": {}}


def load_manifest(force: bool = False) -> dict[str, Any]:
    """Load media manifest with short RAM cache."""
    global _manifest_cache

    now = time.monotonic()
    if not force and _manifest_cache and _manifest_cache[0] > now:
        return _manifest_cache[1]

    if not MANIFEST_PATH.exists():
        data = _empty_manifest()
        _manifest_cache = (now + MANIFEST_CACHE_TTL_SEC, data)
        return data

    try:
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Manifest root must be object")
        assets = parsed.get("assets", {})
        if not isinstance(assets, dict):
            raise ValueError("Manifest 'assets' must be object")
        data = {
            "version": int(parsed.get("version", 1)),
            "generated_at": parsed.get("generated_at"),
            "assets": assets,
        }
        _manifest_cache = (now + MANIFEST_CACHE_TTL_SEC, data)
        return data
    except Exception:
        logger.exception("Failed to load web media manifest: %s", MANIFEST_PATH)
        data = _empty_manifest()
        _manifest_cache = (now + MANIFEST_CACHE_TTL_SEC, data)
        return data


def get_media_asset(key: str) -> dict[str, Any] | None:
    """Return single media asset metadata by key."""
    manifest = load_manifest(force=False)
    assets = manifest.get("assets", {})
    item = assets.get(key)
    return item if isinstance(item, dict) else None
