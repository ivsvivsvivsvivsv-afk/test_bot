import os
import json
from pathlib import Path
from typing import Optional, Tuple, List

import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

router = Router()

# Interactive state: admin_id -> pending key
_PENDING_KEY: dict[int, str] = {}


def _parse_admin_ids_from_env() -> List[int]:
    raw = os.getenv("ADMIN_IDS", "")
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def _is_admin(user_id: int) -> bool:
    # 1) ENV
    env_ids = _parse_admin_ids_from_env()
    if env_ids:
        return user_id in env_ids

    # 2) config.py fallback
    try:
        import config  # type: ignore
        cfg_ids = getattr(config, "ADMIN_IDS", None)
        if isinstance(cfg_ids, (list, tuple, set)):
            return user_id in set(int(x) for x in cfg_ids)
    except Exception:
        pass

    return False


def _allowed_keys() -> List[str]:
    """Allowed keys are taken from images.json if present; otherwise returns a sensible default set."""
    # Try to read keys from repo file (optional, just to prevent typos)
    for p in (Path("/app/images.json"), Path("images.json")):
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    keys = [k for k in data.keys() if isinstance(k, str) and k.strip()]
                    keys.sort()
                    if keys:
                        return keys
        except Exception:
            continue

    # fallback minimal set
    return sorted([
        "img_start_portal",
        "img_class_choice",
        "img_weapon_choice",
        "img_weapon_other_ask",
        "img_round_1_intro",
        "img_round_1_intro_marketing",
        "img_round_1_intro_analytics",
        "img_round_1_intro_copywriting",
        "img_round_1_intro_design",
        "img_round_1_intro_management",
        "img_round_1_intro_video",
        "img_round_1_intro_other",
        "img_round_2_intro",
        "img_round_3_intro",
        "img_answer_prompt",
        "img_result_correct",
        "img_result_wrong",
        "img_moral",
        "img_workshop_ask_phone",
        "img_workshop_ask_email",
        "img_workshop_final",
        "img_arena_intro",
        "img_arena_ask_phone",
        "img_arena_complete",
    ])


def _db_path() -> str:
    """Pick the same DB path your bot uses (Amvera persists /data)."""
    # Explicit env
    for var in ("DB_PATH", "DATABASE_PATH"):
        v = os.getenv(var)
        if v:
            return v

    # Try database module constants
    try:
        import database  # type: ignore
        for attr in ("DB_PATH", "DATABASE_PATH"):
            if hasattr(database, attr):
                val = getattr(database, attr)
                return str(val)
    except Exception:
        pass

    # Default (matches your earlier logs)
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


def _normalize_kind(kind: str) -> str:
    kind = (kind or "photo").strip().lower()
    if kind in ("doc", "document"):
        return "doc"
    return "photo"


async def _ensure_images_table(db: aiosqlite.Connection) -> None:
    await db.execute(_images_table_sql())


async def set_image(key: str, kind: str, file_id: str) -> None:
    key = (key or "").strip()
    file_id = (file_id or "").strip()
    if not key or not file_id:
        return
    kind = _normalize_kind(kind)

    async with aiosqlite.connect(_db_path()) as db:
        await _ensure_images_table(db)
        await db.execute(
            """
            INSERT INTO images(key, kind, file_id, updated_at)
            VALUES(?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
              kind=excluded.kind,
              file_id=excluded.file_id,
              updated_at=CURRENT_TIMESTAMP
            """,
            (key, kind, file_id),
        )
        await db.commit()


async def get_image(key: str) -> Optional[Tuple[str, str]]:
    key = (key or "").strip()
    if not key:
        return None
    async with aiosqlite.connect(_db_path()) as db:
        await _ensure_images_table(db)
        cur = await db.execute("SELECT kind, file_id FROM images WHERE key = ?", (key,))
        row = await cur.fetchone()
        return (row[0], row[1]) if row else None


async def delete_image(key: str) -> None:
    key = (key or "").strip()
    if not key:
        return
    async with aiosqlite.connect(_db_path()) as db:
        await _ensure_images_table(db)
        await db.execute("DELETE FROM images WHERE key = ?", (key,))
        await db.commit()


async def list_saved_keys() -> List[str]:
    async with aiosqlite.connect(_db_path()) as db:
        await _ensure_images_table(db)
        cur = await db.execute("SELECT key FROM images ORDER BY key")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def _deny(msg: Message) -> None:
    await msg.answer(
        "⛔️ Доступ только админу.\n"
        f"Твой Telegram ID: {msg.from_user.id}\n"
        "Добавь его в ADMIN_IDS и перезапусти сервис."
    )


@router.message(Command("imgwhere"))
async def imgwhere(msg: Message):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)
    p = _db_path()
    await msg.answer(f"DB path: {p}")


@router.message(Command("imgkeys"))
async def imgkeys(msg: Message):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)

    keys = _allowed_keys()
    saved = set(await list_saved_keys())

    lines = []
    for k in keys:
        lines.append(f"✅ {k}" if k in saved else f"— {k}")

    await msg.answer("Ключи (✅ = уже сохранено):\n" + "\n".join(lines))


@router.message(Command("imgset"))
async def imgset(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)
    if not command.args:
        return await msg.answer("Используй: /imgset <key>\nПример: /imgset img_start_portal")

    key = command.args.strip()
    if key not in _allowed_keys():
        return await msg.answer(f"Нет такого ключа: {key}\nПроверь /imgkeys")

    _PENDING_KEY[msg.from_user.id] = key
    await msg.answer(f"Ок. Теперь отправь фото для ключа: {key}")


@router.message(F.photo)
async def on_photo(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    key = _PENDING_KEY.get(msg.from_user.id)
    if not key:
        return

    file_id = msg.photo[-1].file_id
    await set_image(key, "photo", file_id)
    _PENDING_KEY.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено\n{key} = {file_id}")


@router.message(Command("imgget"))
async def imgget(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)
    if not command.args:
        return await msg.answer("Используй: /imgget <key>")

    key = command.args.strip()
    row = await get_image(key)
    await msg.answer(f"{key} = {row}")


@router.message(Command("imgdel"))
async def imgdel(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)
    if not command.args:
        return await msg.answer("Используй: /imgdel <key>")

    key = command.args.strip()
    await delete_image(key)
    await msg.answer(f"🗑️ Удалено: {key}")


@router.message(Command("imgtest"))
async def imgtest(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        return await _deny(msg)
    if not command.args:
        return await msg.answer("Используй: /imgtest <key>")

    key = command.args.strip()
    row = await get_image(key)
    if not row:
        return await msg.answer(f"Нет изображения для ключа: {key}")

    kind, file_id = row
    if kind == "doc":
        await msg.answer_document(file_id)
    else:
        await msg.answer_photo(file_id)
