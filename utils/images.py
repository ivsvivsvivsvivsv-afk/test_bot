import os
from typing import Optional, Tuple

import aiosqlite


def _db_path() -> str:
    for var in ("DB_PATH", "DATABASE_PATH"):
        v = os.getenv(var)
        if v:
            return v
    try:
        import database  # type: ignore
        for attr in ("DB_PATH", "DATABASE_PATH"):
            if hasattr(database, attr):
                return str(getattr(database, attr))
    except Exception:
        pass
    return "/data/bot.db"


def _images_table_sql() -> str:
    return (
        "CREATE TABLE IF NOT EXISTS images ("
        "key TEXT PRIMARY KEY,"
        "kind TEXT NOT NULL,"
        "file_id TEXT NOT NULL,"
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ");"
    )


async def _ensure_images_table(db: aiosqlite.Connection) -> None:
    await db.execute(_images_table_sql())


async def get_image(key: str) -> Optional[Tuple[str, str]]:
    key = (key or "").strip()
    if not key:
        return None
    async with aiosqlite.connect(_db_path()) as db:
        await _ensure_images_table(db)
        cur = await db.execute("SELECT kind, file_id FROM images WHERE key = ?", (key,))
        row = await cur.fetchone()
        return (row[0], row[1]) if row else None


async def send_image(target, key: str) -> bool:
    """Send image by key to Message or CallbackQuery.message.

    Returns True if sent, False if no image.
    """
    row = await get_image(key)
    if not row:
        return False

    kind, file_id = row

    # allow passing CallbackQuery or Message
    if hasattr(target, "message") and target.message is not None:
        target = target.message

    if kind == "doc":
        await target.answer_document(file_id)
    else:
        await target.answer_photo(file_id)
    return True


# Backward-compatible alias names (in case your code calls them)
send_image_by_key = send_image
