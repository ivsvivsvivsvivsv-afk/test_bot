import os
import json
import aiosqlite
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject

router = Router()

# --- Config ---
DEFAULT_DB_PATH = "/data/bot.db"  # matches your logs: Database path: /data/bot.db

# Keys registry (optional): if images.json exists, we use its keys to prevent typos.
DEFAULT_KEYS = [
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
]

# When you run inside Amvera, /app is your code dir; images.json may exist there from repo.
IMAGES_KEYS_JSON = os.getenv("IMAGES_KEYS_JSON", "/app/images.json")

_pending_key: dict[int, str] = {}  # admin_id -> key


def _parse_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "").strip()
    if not raw:
        return set()
    out = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _is_admin(user_id: int) -> bool:
    admin_ids = _parse_admin_ids()
    return (user_id in admin_ids) if admin_ids else False


def _get_db_path() -> str:
    # Prefer DB_PATH if you have it in env, otherwise default to /data/bot.db
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


def _load_allowed_keys() -> list[str]:
    # If images.json exists in repo, use its keys as registry (values are ignored).
    try:
        if os.path.exists(IMAGES_KEYS_JSON):
            with open(IMAGES_KEYS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return sorted(list(data.keys()))
    except Exception:
        pass
    return sorted(DEFAULT_KEYS)


async def _ensure_table(db_path: str) -> None:
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


async def _set_image(db_path: str, key: str, kind: str, file_id: str) -> None:
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO images(key, kind, file_id, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
              kind=excluded.kind,
              file_id=excluded.file_id,
              updated_at=excluded.updated_at
            """,
            (key, kind, file_id, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def _get_image(db_path: str, key: str):
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT kind, file_id, updated_at FROM images WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row  # None or (kind, file_id, updated_at)


async def _del_image(db_path: str, key: str) -> bool:
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("DELETE FROM images WHERE key=?", (key,))
        await db.commit()
        return cur.rowcount > 0


async def _list_saved_keys(db_path: str) -> list[str]:
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT key FROM images ORDER BY key") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def _send_image(msg: Message, kind: str, file_id: str) -> None:
    if kind == "document":
        await msg.answer_document(file_id)
    else:
        await msg.answer_photo(file_id)


@router.message(Command("imgwhere"))
async def imgwhere(msg: Message):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    db_path = _get_db_path()
    await msg.answer(
        f"DB_PATH: {db_path}\n"
        f"Exists: {os.path.exists(db_path)}\n"
        f"Keys registry: {IMAGES_KEYS_JSON} (exists={os.path.exists(IMAGES_KEYS_JSON)})"
    )


@router.message(Command("imgkeys"))
async def imgkeys(msg: Message):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    keys = _load_allowed_keys()
    await msg.answer("Ключи:\n" + "\n".join(keys))


@router.message(Command("imgkeys_saved"))
async def imgkeys_saved(msg: Message):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    db_path = _get_db_path()
    keys = await _list_saved_keys(db_path)
    await msg.answer("Сохранённые ключи:\n" + ("\n".join(keys) if keys else "(пусто)"))


@router.message(Command("imgset"))
async def imgset(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    if not command.args:
        await msg.answer("Используй: /imgset <key>\nПример: /imgset img_start_portal")
        return

    key = command.args.strip()
    allowed = set(_load_allowed_keys())
    if key not in allowed:
        await msg.answer(f"Нет такого ключа: {key}\nСмотри список: /imgkeys")
        return

    _pending_key[msg.from_user.id] = key
    await msg.answer(f"Ок. Теперь отправь фото для ключа:\n{key}")


@router.message(F.photo)
async def on_photo(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    key = _pending_key.get(msg.from_user.id)
    if not key:
        return

    file_id = msg.photo[-1].file_id
    db_path = _get_db_path()
    await _set_image(db_path, key, "photo", file_id)
    _pending_key.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено\n{key} = {file_id}\n(в БД: {db_path})")


@router.message(F.document)
async def on_document(msg: Message):
    if not _is_admin(msg.from_user.id):
        return
    key = _pending_key.get(msg.from_user.id)
    if not key:
        return

    # for images sent as document (no compression)
    file_id = msg.document.file_id
    db_path = _get_db_path()
    await _set_image(db_path, key, "document", file_id)
    _pending_key.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено\n{key} = {file_id}\n(в БД: {db_path})")


@router.message(Command("imgget"))
async def imgget(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    if not command.args:
        await msg.answer("Используй: /imgget <key>")
        return
    key = command.args.strip()
    db_path = _get_db_path()
    row = await _get_image(db_path, key)
    if not row:
        await msg.answer(f"{key}: (нет)")
        return
    kind, file_id, updated_at = row
    await msg.answer(f"{key}: {kind} {file_id}\nupdated_at: {updated_at}")


@router.message(Command("imgdel"))
async def imgdel(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    if not command.args:
        await msg.answer("Используй: /imgdel <key>")
        return
    key = command.args.strip()
    db_path = _get_db_path()
    ok = await _del_image(db_path, key)
    await msg.answer("🗑️ Очищено" if ok else "Ключа не было")


@router.message(Command("imgtest"))
async def imgtest(msg: Message, command: CommandObject):
    if not _is_admin(msg.from_user.id):
        await msg.answer(
            f"⛔️ Доступ только админу.\n"
            f"Твой ID: {msg.from_user.id}\n"
            f"Добавь его в ADMIN_IDS (через запятую) и задеплой."
        )
        return
    if not command.args:
        await msg.answer("Используй: /imgtest <key>")
        return
    key = command.args.strip()
    db_path = _get_db_path()
    row = await _get_image(db_path, key)
    if not row:
        await msg.answer(f"{key}: (нет в БД)")
        return
    kind, file_id, _ = row
    await msg.answer(f"Отправляю {key}…")
    await _send_image(msg, kind, file_id)
