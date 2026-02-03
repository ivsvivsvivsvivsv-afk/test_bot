import os
import aiosqlite
from typing import Optional, Tuple, Any, Iterable, Union

# Persistent DB location (Amvera keeps /data)
DEFAULT_DB_PATH = "/data/bot.db"


def _db_path() -> str:
    # Prefer explicit envs if you ever set them
    return (
        os.getenv("DB_PATH")
        or os.getenv("DATABASE_PATH")
        or os.getenv("DATABASE_URL")  # in case you pass a file path here
        or DEFAULT_DB_PATH
    )


async def _ensure_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,         -- 'photo' or 'document'
            file_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    await conn.commit()


async def get_image(key: Any) -> Optional[Tuple[str, str]]:
    """Return (kind, file_id) or None."""
    if key is None:
        return None
    key = str(key)
    db_path = _db_path()
    async with aiosqlite.connect(db_path) as conn:
        await _ensure_table(conn)
        async with conn.execute(
            "SELECT kind, file_id FROM images WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return row[0], row[1]


def _unwrap_target(target: Any):
    """Accept Message or CallbackQuery; return object that has answer_* methods."""
    # If it's a CallbackQuery, prefer its message
    msg = getattr(target, "message", None)
    return msg if msg is not None else target


async def _send_single(target: Any, key: str) -> bool:
    t = _unwrap_target(target)
    rec = await get_image(key)
    if not rec:
        return False

    kind, file_id = rec
    if kind == "document":
        await t.answer_document(file_id)
    else:
        await t.answer_photo(file_id)
    return True


async def send_image_if_exists(target: Any, key: Union[str, Iterable[str]]) -> bool:
    """
    Try to send image for key(s). Returns True if sent.

    - If `key` is a string: tries that key.
    - If `key` is a list/tuple/set/etc: tries keys in order, sends the first that exists.

    Supports both photo and document kinds stored in DB.
    """

    # IMPORTANT: some handlers pass a list of fallbacks, e.g.
    # send_image_if_exists(message, ['img_already_played', 'img_start_portal'])
    if isinstance(key, (list, tuple, set)):
        for k in key:
            if k and await _send_single(target, str(k)):
                return True
        return False

    return await _send_single(target, str(key))


async def send_photo_with_caption(
    target: Any,
    key: Union[str, Iterable[str]],
    caption: str,
    reply_markup: Any = None
) -> bool:
    """
    Send photo with caption and optional reply_markup.
    Returns True if photo was sent, False otherwise.
    If no photo found, returns False (caller should send text message instead).
    """
    t = _unwrap_target(target)
    
    # Handle list of keys (fallbacks)
    keys_to_try = [key] if isinstance(key, str) else list(key)
    
    for k in keys_to_try:
        if not k:
            continue
        rec = await get_image(str(k))
        if rec:
            kind, file_id = rec
            if kind == "document":
                await t.answer_document(file_id, caption=caption, reply_markup=reply_markup)
            else:
                await t.answer_photo(file_id, caption=caption, reply_markup=reply_markup)
            return True
    
    return False


def resolve_round_intro_image_key(weapon: Optional[str], round_num: int) -> str:
    """
    Key resolver used by quest flow:
      - Round 1 depends on chosen profession/weapon: img_round_1_intro_<weapon>
      - Other rounds: img_round_<n>_intro
    Falls back should be handled by caller (try generic key if specific missing).
    """
    if round_num == 1 and weapon:
        return f"img_round_1_intro_{weapon}"
    return f"img_round_{round_num}_intro"


# Backwards/forwards compatibility aliases (in case other files import these)
async def send_image_by_key(target: Any, key: Union[str, Iterable[str]]) -> bool:
    return await send_image_if_exists(target, key)
