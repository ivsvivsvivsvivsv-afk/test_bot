#!/usr/bin/env python3
"""
Загрузка картинок в sandbox-бота для получения file_id.

Использование:
1. Положите картинки в content/media/ (или --folder PATH)
   Ожидаемые имена: img_start.jpg, img_prepare.jpg, img_free_boss.jpg и т.д.
2. Запустите: APP_ENV=sandbox python scripts/upload_sandbox_media.py
   Токен берётся из .env (BOT_TOKEN), либо передайте --token
   Chat для отправки: ADMIN_IDS[0] (первый админ получит картинки)
3. Скрипт выведет SANDBOX_MEDIA_FILE_IDS — вставьте в utils/media_ids.py
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Keys from MEDIA_FILE_IDS — ожидаемые имена файлов
KEY_TO_FILENAME: dict[str, str] = {
    "img_start": "img_start.jpg",
    "img_prepare": "img_prepare.jpg",
    "img_free_boss": "img_free_boss.jpg",
    "img_proff": "img_proff.jpg",
    "img_analit": "img_analit.jpg",
    "img_copy": "img_copy.jpg",
    "img_design": "img_design.jpg",
    "img_managment": "img_managment.jpg",
    "img_marketing": "img_marketing.jpg",
    "img_video": "img_video.jpg",
    "img_other": "img_other.jpg",
    "img_kill": "img_kill.jpg",
    "img_gidratt": "img_gidratt.jpg",
    "img_win": "img_win.jpg",
    "img_lose": "img_lose.jpg",
    "img_stark": "img_stark.jpg",
    "img_final": "img_final.jpg",
}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Upload media to sandbox bot, get file_ids")
    parser.add_argument("--folder", default="content/media", help="Folder with images")
    parser.add_argument("--token", help="BOT_TOKEN (or from .env)")
    parser.add_argument("--chat-id", type=int, help="Chat to send photos to (default: first ADMIN_IDS)")
    parser.add_argument("--dry-run", action="store_true", help="Only list files, do not upload")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    folder = project_root / args.folder
    if not folder.is_dir():
        print(f"[FAIL] Folder not found: {folder}")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
    token = args.token or os.getenv("BOT_TOKEN", "").strip()
    if not token:
        print("[FAIL] BOT_TOKEN required. Set in .env or pass --token")
        sys.exit(1)

    admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
    chat_id = args.chat_id
    if chat_id is None and admin_ids:
        chat_id = admin_ids[0]
    if chat_id is None:
        print("[FAIL] Need --chat-id or ADMIN_IDS in .env (to send photos)")
        sys.exit(1)

    found: dict[str, Path] = {}
    for key, filename in KEY_TO_FILENAME.items():
        p = folder / filename
        if p.exists():
            found[key] = p
        else:
            for ext in (".png", ".webp", ".jpeg"):
                alt = folder / (Path(filename).stem + ext)
                if alt.exists():
                    found[key] = alt
                    break

    if not found:
        print(f"[FAIL] No images in {folder}. Expected: img_start.jpg, img_prepare.jpg, ...")
        print("Copy your graphics folder to content/media/ and run again.")
        sys.exit(1)
    print(f"Found {len(found)} images")

    if args.dry_run:
        for k, p in found.items():
            print(f"  {k}: {p.name}")
        return

    from aiogram import Bot
    from aiogram.types import FSInputFile

    bot = Bot(token=token)
    result: dict[str, str] = {}
    try:
        for key, path in found.items():
            print(f"  Uploading {key}...", end=" ", flush=True)
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=FSInputFile(path),
                caption=f"#{key}",
            )
            fid = msg.photo[-1].file_id if msg.photo else ""
            if fid:
                result[key] = fid
                print(f"OK {fid[:20]}...")
            else:
                print("FAIL (no file_id)")
    finally:
        await bot.session.close()

    if result:
        print("\n# Вставьте в utils/media_ids.py → SANDBOX_MEDIA_FILE_IDS:")
        print("SANDBOX_MEDIA_FILE_IDS: dict[str, str] = {")
        for k, v in sorted(result.items()):
            print(f'    "{k}": "{v}",')
        print("}")


if __name__ == "__main__":
    asyncio.run(main())
