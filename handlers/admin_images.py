import json
from pathlib import Path
from typing import Dict

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import ADMIN_IDS
from database import set_image, get_image, delete_image, list_image_keys, DB_PATH
from utils.images import send_image_if_exists

router = Router()

_pending_key: Dict[int, str] = {}  # admin_user_id -> image_key


def _is_admin(user_id: int) -> bool:
    return user_id in set(ADMIN_IDS or [])



def _allowed_keys() -> list[str]:
    """Allowed image keys come from images.json (repo) if present."""
    try:
        p = Path("images.json")
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return sorted(list(data.keys()))
    except Exception:
        pass
    # fallback minimal set
    return sorted([
        "img_start_portal",
        "img_already_played",
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



async def _deny(msg: Message) -> bool:
    if _is_admin(msg.from_user.id):
        return False
    await msg.answer(
        "⛔️ Доступ только админу.\n"
        f"Твой Telegram ID: {msg.from_user.id}\n\n"
        "Добавь его в переменную окружения ADMIN_IDS (через запятую) и перезапусти бота.\n"
        "Пример: ADMIN_IDS=190421400,758800494"
    )
    return True


@router.message(Command("imgwhere"))
async def imgwhere(msg: Message):
    if await _deny(msg):
        return
    try:
        keys_in_db = await list_image_keys()
        count = len(keys_in_db)
    except Exception:
        count = 0
    await msg.answer(
        "Хранилище картинок: SQLite (персистентно в /data)\n"
        f"DB_PATH: {DB_PATH}\n"
        f"Сохранено ключей: {count}\n\n"
        "Подсказка: /imgkeys (список ключей), /imgset <key> (записать), /imgget <key> (проверить)."
    )


@router.message(Command("imgkeys"))
async def imgkeys(msg: Message):
    if await _deny(msg):
        return
    keys = _allowed_keys()
    await msg.answer("Ключи картинок:\n" + "\n".join(keys))


@router.message(Command("imgset"))
async def imgset_cmd(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgset <key>\nПример: /imgset img_round_1_intro_marketing")
        return

    key = command.args.strip()
    keys = set(_allowed_keys())
    if key not in keys:
        await msg.answer(
            f"Нет такого ключа: {key}\n"
            "Проверь /imgkeys. Если хочешь новый ключ — добавь его в images.json и задеплой."
        )
        return

    _pending_key[msg.from_user.id] = key
    await msg.answer(f"Ок. Теперь отправь картинку (как Фото) для ключа:\n{key}")


@router.message(Command("imgget"))
async def imgget_cmd(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgget <key>")
        return
    key = command.args.strip()
    row = await get_image(key)
    if not row:
        await msg.answer(f"{key} = (пусто)")
        return
    kind, file_id = row
    await msg.answer(f"{key} = {kind}:{file_id}")


@router.message(Command("imgdel"))
async def imgdel_cmd(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgdel <key>")
        return
    key = command.args.strip()
    await delete_image(key)
    await msg.answer(f"🗑️ Очищено: {key}")


@router.message(Command("imgtest"))
async def imgtest_cmd(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgtest <key>")
        return
    key = command.args.strip()
    row = await get_image(key)
    await msg.answer(f"{key} = {row if row else '(пусто)'}")
    await send_image_if_exists(msg, [key])


@router.message(F.photo)
async def on_photo(msg: Message):
    if await _deny(msg):
        return
    key = _pending_key.get(msg.from_user.id)
    if not key:
        return
    file_id = msg.photo[-1].file_id  # max size
    await set_image(key, "photo", file_id)
    _pending_key.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено\n{key} = {file_id}")


@router.message(F.document)
async def on_document(msg: Message):
    if await _deny(msg):
        return
    key = _pending_key.get(msg.from_user.id)
    if not key:
        return
    file_id = msg.document.file_id
    await set_image(key, "doc", file_id)
    _pending_key.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено (doc)\n{key} = {file_id}")
