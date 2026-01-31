import json
from pathlib import Path
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import ADMIN_IDS

router = Router()

IMAGES_PATH = Path("images.json")
_pending_key: Dict[int, str] = {}  # admin_user_id -> image_key


def _is_admin(user_id: int) -> bool:
    return user_id in set(ADMIN_IDS or [])


def _load_images() -> dict:
    if not IMAGES_PATH.exists():
        return {}
    try:
        data = json.loads(IMAGES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_images(data: dict) -> None:
    IMAGES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


@router.message(Command("imgkeys"))
async def imgkeys(msg: Message):
    if await _deny(msg):
        return
    data = _load_images()
    if not data:
        await msg.answer("images.json пустой или не найден.")
        return
    keys = sorted(data.keys())
    await msg.answer("Ключи картинок:\n" + "\n".join(keys))


@router.message(Command("imgset"))
async def imgset(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgset <key>\nПример: /imgset img_round_1_intro_marketing")
        return

    key = command.args.strip()
    data = _load_images()
    if key not in data:
        await msg.answer(
            f"Нет такого ключа в images.json: {key}\n"
            "Сначала добавь ключ в images.json (или используй /imgkeys)."
        )
        return

    _pending_key[msg.from_user.id] = key
    await msg.answer(f"Ок. Теперь отправь картинку (как Фото или как Документ) для ключа:\n{key}")


@router.message(Command("imgget"))
async def imgget(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgget <key>")
        return
    key = command.args.strip()
    data = _load_images()
    await msg.answer(f"{key} = {data.get(key, '')}")


@router.message(Command("imgdel"))
async def imgdel(msg: Message, command: CommandObject):
    if await _deny(msg):
        return
    if not command.args:
        await msg.answer("Используй: /imgdel <key>")
        return
    key = command.args.strip()
    data = _load_images()
    if key not in data:
        await msg.answer(f"Нет такого ключа: {key}")
        return
    data[key] = ""
    _save_images(data)
    await msg.answer(f"🗑️ Очищено: {key}")


@router.message(F.photo)
async def on_photo(msg: Message):
    if await _deny(msg):
        return
    key = _pending_key.get(msg.from_user.id)
    if not key:
        return
    file_id = msg.photo[-1].file_id  # max size
    data = _load_images()
    data[key] = file_id
    _save_images(data)
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
    data = _load_images()
    data[key] = file_id
    _save_images(data)
    _pending_key.pop(msg.from_user.id, None)
    await msg.answer(f"✅ Сохранено\n{key} = {file_id}")
