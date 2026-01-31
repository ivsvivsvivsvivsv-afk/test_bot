import json
from pathlib import Path

TEXTS_PATH = Path("texts_hydra_v5.json")

with TEXTS_PATH.open(encoding="utf-8") as f:
    data = json.load(f)

MESSAGES = data["messages"]
BUTTONS = data["buttons"]
ROUND_NAMES = data.get("round_names", {})
WEAPON_LABELS = data.get("weapon_labels", {})
ADMIN_TEMPLATES = data.get("admin", {})
URLS = data.get("urls", {})
REMINDERS = data.get("reminders", {})
