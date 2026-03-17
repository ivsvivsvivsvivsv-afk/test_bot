"""
ContentManager — facade over ContentRegistry for backward compatibility.

All calls use bundle_id="default". New code should use ContentRegistry.get(bundle_id, key)
with bundle_id from ScenarioContext.
"""

from __future__ import annotations

from typing import Any

from utils.content_registry import get as _registry_get
from utils.content_registry import get_raw as _registry_get_raw
from utils.content_registry import load_all as _registry_load_all


class ContentManager:
    """
    Facade over ContentRegistry. Uses bundle_id="default".
    """

    _loaded: bool = False

    @classmethod
    def load(cls, path: str = "content/texts.json") -> "ContentManager":
        """Initialize ContentRegistry. Path ignored for backward compat (legacy → default)."""
        _registry_load_all()
        cls._loaded = True
        return cls

    @classmethod
    def instance(cls) -> "ContentManager":
        if not cls._loaded:
            raise RuntimeError("ContentManager is not loaded. Call ContentManager.load() first.")
        return cls

    @classmethod
    def reset(cls) -> None:
        from utils.content_registry import reset as _registry_reset

        _registry_reset()
        cls._loaded = False

    @classmethod
    def get(cls, key: str, **kwargs: Any) -> str:
        return _registry_get("default", key, **kwargs)

    @classmethod
    def get_raw(cls, key: str) -> Any:
        return _registry_get_raw("default", key)
