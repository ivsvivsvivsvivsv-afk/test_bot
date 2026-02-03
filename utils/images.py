import os
import aiosqlite
from typing import Optional, Tuple, Any, Iterable, Union

# Persistent DB location (Amvera keeps /data)
DEFAULT_DB_PATH = "/data/bot.db"


def _db_path() -> str:
    return (
        os.getenv("DB_PATH")
        or os.getenv("DATABASE_PATH")
        or os.getenv("DATABASE_URL")
        or DEFAULT_DB_PATH
    )


async def _ensure_table(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
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
    msg = getattr(target, "message", None)
    return msg if msg is not None else target


async def _send_single(target: Any, key: str) -> Optional[int]:
    """Send image by key. Returns message_id if sent, None otherwise."""
    t = _unwrap_target(target)
    rec = await get_image(key)
    if not rec:
        return None

    kind, file_id = rec
    if kind == "document":
        sent_msg = await t.answer_document(file_id)
    else:
        sent_msg = await t.answer_photo(file_id)
    return sent_msg.message_id


async def send_image_if_exists(target: Any, key: Union[str, Iterable[str]]) -> Optional[int]:
    """
    Try to send image for key(s). Returns message_id if sent, None otherwise.
    """
    if isinstance(key, (list, tuple, set)):
        for k in key:
            if k:
                msg_id = await _send_single(target, str(k))
                if msg_id:
                    return msg_id
        return None

    return await _send_single(target, str(key))


async def send_photo_with_caption(
    target: Any,
    key: Union[str, Iterable[str]],
    caption: str,
    reply_markup: Any = None
) -> Optional[int]:
    """
    Send photo with caption and optional reply_markup.
    Returns message_id if photo was sent, None otherwise.
    
    Note: Telegram caption limit is 1024 chars - will be truncated if longer.
    """
    t = _unwrap_target(target)
    
    keys_to_try = [key] if isinstance(key, str) else list(key)
    
    # Truncate caption if too long (Telegram limit is 1024)
    if len(caption) > 1024:
        caption = caption[:1021] + "..."
    
    for k in keys_to_try:
        if not k:
            continue
        rec = await get_image(str(k))
        if rec:
            kind, file_id = rec
            if kind == "document":
                sent_msg = await t.answer_document(file_id, caption=caption, reply_markup=reply_markup)
            else:
                sent_msg = await t.answer_photo(file_id, caption=caption, reply_markup=reply_markup)
            return sent_msg.message_id
    
    return None


async def delete_message_safe(bot: Any, chat_id: int, message_id: Optional[int]) -> bool:
    """Safely delete a message. Returns True if deleted, False otherwise."""
    if not message_id:
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception:
        return False


def resolve_round_intro_image_key(weapon: Optional[str], round_num: int) -> str:
    """
    Key resolver used by quest flow:
      - Round 1 depends on chosen profession/weapon: img_round_1_intro_<weapon>
      - Other rounds: img_round_<n>_intro
    """
    if round_num == 1 and weapon:
        return f"img_round_1_intro_{weapon}"
    return f"img_round_{round_num}_intro"


# Backwards compatibility alias
async def send_image_by_key(target: Any, key: Union[str, Iterable[str]]) -> Optional[int]:
    return await send_image_if_exists(target, key)
