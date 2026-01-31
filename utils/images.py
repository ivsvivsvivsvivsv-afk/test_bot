import os
import aiosqlite

DEFAULT_DB_PATH = "/data/bot.db"


def get_db_path() -> str:
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


async def ensure_images_table() -> None:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
              key TEXT PRIMARY KEY,
              kind TEXT NOT NULL,
              file_id TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def get_image(key: str):
    db_path = get_db_path()
    await ensure_images_table()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT kind, file_id FROM images WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row  # None or (kind, file_id)


async def send_image_by_key(message, key: str) -> bool:
    row = await get_image(key)
    if not row:
        return False
    kind, file_id = row
    try:
        if kind == "document":
            await message.answer_document(file_id)
        else:
            await message.answer_photo(file_id)
        return True
    except Exception:
        return False
