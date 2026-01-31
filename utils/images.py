import json
from pathlib import Path
from typing import Optional

IMAGES_PATH = Path("images.json")

def _load_images() -> dict:
    if not IMAGES_PATH.exists():
        return {}
    try:
        data = json.loads(IMAGES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def get_image_file_id(image_key: str) -> Optional[str]:
    """
    Returns Telegram file_id for given image key.
    Empty/blank values are treated as missing.
    """
    data = _load_images()
    value = data.get(image_key)
    if not value:
        return None
    value = str(value).strip()
    return value or None

def resolve_round_intro_image_key(round_num: int, weapon: str) -> list[str]:
    """
    Returns ordered list of candidate keys for round intro image.
    Requirement: round 1 intro can depend on profession (weapon).
    """
    weapon = (weapon or "other").strip().lower()
    keys = []
    # round 1: per-profession first, then fallback
    if round_num == 1:
        keys.append(f"img_round_1_intro_{weapon}")
    keys.append(f"img_round_{round_num}_intro")
    return keys

async def send_image_if_exists(message, image_key_candidates: list[str]) -> bool:
    """
    Sends first existing image (by file_id) and returns True if sent.
    Does nothing if no file_id configured.
    """
    for key in image_key_candidates:
        file_id = get_image_file_id(key)
        if file_id:
            await message.answer_photo(file_id)
            return True
    return False
