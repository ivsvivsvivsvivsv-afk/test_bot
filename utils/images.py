from typing import Optional, List, Sequence

from database import get_image

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


def _normalize_kind_and_id(kind: Optional[str], file_id: Optional[str]) -> tuple[str, str]:
    """Backwards compatible: supports values stored as 'photo:<id>' / 'doc:<id>' in file_id."""
    k = (kind or "photo").strip().lower()
    fid = (file_id or "").strip()

    # If old format is in fid itself
    if ":" in fid and k in ("photo", "doc", "document"):
        prefix, rest = fid.split(":", 1)
        prefix = prefix.strip().lower()
        rest = rest.strip()
        if prefix in ("photo", "doc") and rest:
            return prefix, rest

    if k == "document":
        k = "doc"
    if k not in ("photo", "doc"):
        k = "photo"
    return k, fid


async def send_image_if_exists(message, image_key_candidates: Sequence[str]) -> bool:
    """Sends first existing image (stored in DB) and returns True if sent."""
    for key in image_key_candidates:
        try:
            row = await get_image(key)
        except Exception:
            row = None

        if not row:
            continue

        kind, file_id = row[0], row[1]
        kind, file_id = _normalize_kind_and_id(kind, file_id)
        if not file_id:
            continue

        try:
            if kind == "doc":
                await message.answer_document(file_id)
            else:
                await message.answer_photo(file_id)
            return True
        except Exception:
            # Try alternative method
            try:
                await message.answer_document(file_id)
                return True
            except Exception:
                continue
    return False
