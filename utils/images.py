import json
import os
from pathlib import Path
from typing import Optional, List

def _default_images_path() -> Path:
    # 1) explicit env
    env_path = os.getenv("IMAGES_PATH")
    if env_path:
        return Path(env_path)
    # 2) common container path
    app_path = Path("/app/images.json")
    if app_path.exists():
        return app_path
    # 3) repo root
    return Path("images.json")

IMAGES_PATH = _default_images_path()

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
    if value is None:
        return None
    value = str(value).strip()
    return value or None

def resolve_round_intro_image_key(round_num: int, weapon: str) -> List[str]:
    """
    Returns ordered list of candidate keys for round intro image.
    Round 1 intro can depend on profession (weapon).
    """
    weapon = (weapon or "other").strip().lower()
    keys: List[str] = []
    if round_num == 1:
        keys.append(f"img_round_1_intro_{weapon}")
    keys.append(f"img_round_{round_num}_intro")
    return keys

async def send_image_if_exists(message, image_key_candidates: List[str]) -> bool:
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
