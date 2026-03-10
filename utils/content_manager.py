from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict


class ContentManager:
    """
    In-memory text catalog loaded from JSON.
    """

    _instance: "ContentManager | None" = None

    def __init__(self, content: Dict[str, Any]):
        self._content = content

    @classmethod
    def load(cls, path: str) -> "ContentManager":
        file_path = Path(path)
        content = json.loads(file_path.read_text(encoding="utf-8"))
        cls._instance = cls(content)
        return cls._instance

    @classmethod
    def instance(cls) -> "ContentManager":
        if cls._instance is None:
            raise RuntimeError("ContentManager is not loaded. Call ContentManager.load() first.")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @classmethod
    def get(cls, key: str, **kwargs: Any) -> str:
        manager = cls.instance()
        value = manager._content.get(key)
        if value is None:
            raise KeyError(f"Missing text key: {key}")
        if not isinstance(value, str):
            raise TypeError(f"Text key '{key}' is not a string")
        if not kwargs:
            return value
        escaped = {
            field_name: html.escape(str(field_value), quote=True)
            for field_name, field_value in kwargs.items()
        }
        return value.format(**escaped)

    @classmethod
    def get_raw(cls, key: str) -> Any:
        manager = cls.instance()
        if key not in manager._content:
            raise KeyError(f"Missing content key: {key}")
        return manager._content[key]
