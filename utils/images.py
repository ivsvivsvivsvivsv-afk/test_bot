import os
import aiosqlite
from typing import Optional, Tuple, Union

# In Amvera /data is persistent. We default there.
DEFAULT_DB_PATH = os.getenv("DB_PATH") or os.getenv("DATABASE_PATH") or "/data/bot.db"


async def _ensure_images_table(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS images (
            key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            file_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        await db.commit()


async def _get_image(db_path: str, key: str) -> Optional[Tuple[str, str]]:
    await _ensure_images_table(db_path)
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT kind, file_id FROM images WHERE key=?", (key,))
        row = await cur.fetchone()
        await cur.close()
    return row if row else None


async def send_image_if_exists(target, key: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Compatibility helper expected by handlers/start.py:
        from utils.images import send_image_if_exists

    target: aiogram.types.Message or CallbackQuery.message
    key: image key like 'img_start_portal'
    Returns True if an image was found and sent.
    """
    row = await _get_image(db_path, key)
    if not row:
        return False
    kind, file_id = row

    # target can be Message or CallbackQuery or any object with answer_* methods.
    # In aiogram v3, Message has answer_photo/answer_document.
    if kind == "document":
        await target.answer_document(file_id)
    else:
        await target.answer_photo(file_id)
    return True


# Backward/alternative name that some patches used.
async def send_image_by_key(target, key: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    return await send_image_if_exists(target, key, db_path=db_path)
