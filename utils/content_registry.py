"""
ContentRegistry — multi-bundle text catalog for repack/multiversion support.

Bundles: content/bundles/{bundle_id}/texts.json
Legacy: content/texts.json → default bundle
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONTENT_ROOT = Path(__file__).parent.parent / "content"
_BUNDLES_DIR = _CONTENT_ROOT / "bundles"
_LEGACY_TEXTS = _CONTENT_ROOT / "texts.json"

# In-memory cache: bundle_id -> raw dict
_bundles_cache: dict[str, dict[str, Any]] = {}
_loaded = False


def _load_bundle(bundle_id: str) -> dict[str, Any] | None:
    """Load bundle from disk. Returns None on failure."""
    bundle_path = _BUNDLES_DIR / bundle_id / "texts.json"
    if bundle_path.exists():
        try:
            return json.loads(bundle_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(
                "BUNDLE_LOAD_FAILED bundle_id=%s path=%s error=%s",
                bundle_id,
                bundle_path,
                exc,
                extra={"bundle_id": bundle_id},
            )
            return None

    # Legacy: default bundle from content/texts.json
    if bundle_id == "default" and _LEGACY_TEXTS.exists():
        try:
            return json.loads(_LEGACY_TEXTS.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(
                "BUNDLE_LOAD_FAILED legacy default path=%s error=%s",
                _LEGACY_TEXTS,
                exc,
                extra={"bundle_id": "default"},
            )
            return None

    return None


def _get_bundle(bundle_id: str) -> dict[str, Any]:
    """Get bundle dict, with fallback to default."""
    global _bundles_cache
    if bundle_id not in _bundles_cache:
        data = _load_bundle(bundle_id)
        if data is not None:
            _bundles_cache[bundle_id] = data
        else:
            # Fallback to default
            if bundle_id != "default":
                logger.warning(
                    "BUNDLE_LOAD_FAILED fallback to default bundle_id=%s",
                    bundle_id,
                    extra={"bundle_id": bundle_id},
                )
            if "default" not in _bundles_cache:
                default_data = _load_bundle("default")
                _bundles_cache["default"] = default_data if default_data else {}
            return _bundles_cache["default"]
    return _bundles_cache[bundle_id]


def load_all() -> None:
    """Preload default bundle. Called at app startup."""
    global _loaded
    if _loaded:
        return
    _get_bundle("default")
    _loaded = True


def get(bundle_id: str, key: str, **kwargs: Any) -> str:
    """
    Get text by key with optional format placeholders.
    Escapes user-provided values via html.escape.
    """
    bundle = _get_bundle(bundle_id)
    value = bundle.get(key)
    if value is None:
        raise KeyError(f"Missing text key: {key} in bundle {bundle_id}")
    if not isinstance(value, str):
        raise TypeError(f"Text key '{key}' is not a string in bundle {bundle_id}")
    if not kwargs:
        return value
    escaped = {
        k: html.escape(str(v), quote=True)
        for k, v in kwargs.items()
    }
    return value.format(**escaped)


def get_raw(bundle_id: str, key: str) -> Any:
    """Get raw value (string or nested dict) without formatting."""
    bundle = _get_bundle(bundle_id)
    if key not in bundle:
        raise KeyError(f"Missing content key: {key} in bundle {bundle_id}")
    return bundle[key]


def get_bundle(bundle_id: str) -> dict[str, Any]:
    """Return full bundle dict (copy)."""
    return dict(_get_bundle(bundle_id))


def list_bundles() -> list[str]:
    """
    List available bundle IDs.
    Includes: dirs in content/bundles/ + "default" if legacy texts.json exists.
    """
    result: set[str] = set()
    if _BUNDLES_DIR.exists():
        for d in _BUNDLES_DIR.iterdir():
            if d.is_dir() and (d / "texts.json").exists():
                result.add(d.name)
    if _LEGACY_TEXTS.exists():
        result.add("default")
    return sorted(result) if result else ["default"]


def reset() -> None:
    """Clear cache. For tests."""
    global _bundles_cache, _loaded
    _bundles_cache = {}
    _loaded = False
