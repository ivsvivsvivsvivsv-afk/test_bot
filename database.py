import aiosqlite
from pathlib import Path
from typing import Optional


from pathlib import Path
DB_PATH = Path("/data/database.db")



async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,

                state TEXT DEFAULT 'start',
                quest_completed INTEGER DEFAULT 0,

                player_class TEXT,
                weapon TEXT,
                other_sphere TEXT,

                score INTEGER DEFAULT 0,
                round_number INTEGER DEFAULT 0,

                current_statement TEXT,
                current_is_truth INTEGER DEFAULT 0,
                current_wisdom_prompt TEXT,

                phone TEXT,
                email TEXT,

                workshop_registered INTEGER DEFAULT 0,
                arena_registered INTEGER DEFAULT 0,

                quest_started_at INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # images storage (persistent in /data/database.db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                file_id TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # --- auto-migrations (add missing columns safely) ---
        cur = await db.execute("PRAGMA table_info(users)")
        cols = [row[1] async for row in cur]

        async def add_col(sql: str, col: str):
            if col not in cols:
                await db.execute(sql)

        await add_col("ALTER TABLE users ADD COLUMN other_sphere TEXT", "other_sphere")
        await add_col("ALTER TABLE users ADD COLUMN current_wisdom_prompt TEXT", "current_wisdom_prompt")
        await add_col("ALTER TABLE users ADD COLUMN workshop_registered INTEGER DEFAULT 0", "workshop_registered")
        await add_col("ALTER TABLE users ADD COLUMN arena_registered INTEGER DEFAULT 0", "arena_registered")
        await add_col("ALTER TABLE users ADD COLUMN quest_started_at INTEGER", "quest_started_at")

        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        await db.commit()


async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return

    fields = ", ".join([f"{k}=?" for k in kwargs])
    values = list(kwargs.values()) + [user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
        await db.commit()


# -------------------- images helpers --------------------

async def set_image(key: str, kind: str, file_id: str) -> None:
    """Upsert image mapping (key -> (kind, file_id)). kind: 'photo' or 'doc'."""
    key = (key or "").strip()
    kind = (kind or "photo").strip().lower()
    file_id = (file_id or "").strip()
    if not key or not file_id:
        return
    if kind not in ("photo", "doc", "document"):
        kind = "photo"
    if kind == "document":
        kind = "doc"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO images(key, kind, file_id, updated_at)
                 VALUES(?, ?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(key) DO UPDATE SET kind=excluded.kind, file_id=excluded.file_id, updated_at=CURRENT_TIMESTAMP""",
            (key, kind, file_id),
        )
        await db.commit()


async def get_image(key: str):
    """Returns tuple (kind, file_id) or None."""
    key = (key or "").strip()
    if not key:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT kind, file_id FROM images WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row if row else None


async def delete_image(key: str) -> None:
    key = (key or "").strip()
    if not key:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM images WHERE key = ?", (key,))
        await db.commit()


async def list_image_keys() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT key FROM images ORDER BY key")
        rows = await cur.fetchall()
        return [r[0] for r in rows]
