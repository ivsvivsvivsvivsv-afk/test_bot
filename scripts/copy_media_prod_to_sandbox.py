#!/usr/bin/env python3
"""
Копирование file_id из prod в sandbox: скачать картинки через prod-бота и загрузить через sandbox-бота.

Требует: PROD_BOT_TOKEN и SANDBOX_BOT_TOKEN, ADMIN_IDS (для chat_id).
Токены можно взять с сервера: python scripts/copy_media_prod_to_sandbox.py --fetch-from-server

Использование:
  python scripts/copy_media_prod_to_sandbox.py --fetch-from-server
  # или с явными токенами:
  PROD_BOT_TOKEN=... SANDBOX_BOT_TOKEN=... ADMIN_IDS=123456 python scripts/copy_media_prod_to_sandbox.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ключи и file_id от prod (из utils/media_ids.py)
PROD_MEDIA: dict[str, str] = {
    "img_start": "AgACAgIAAxkBAAIG_2mTXxk3cZ9Lst7juDhy2sH-bVsVAALsFGsbDbugSEpmjVsIbKqyAQADAgADeQADOgQ",
    "img_prepare": "AgACAgIAAxkDAAIIoWmq-iNVzfdt19fjd900Flhe1x8GAAIbFmsbqu9YSXczRSmUVU1SAQADAgADeQADOgQ",
    "img_free_boss": "AgACAgIAAxkBAAIHAmmTX0D9v2RiDGmr8rd5Fdkxg59yAALuFGsbDbugSJ2Khynw3Pr1AQADAgADeQADOgQ",
    "img_proff": "AgACAgIAAxkBAAIHBWmTX57E-eM5i9jt6YPBbQrhCsu-AAL5FGsbDbugSIRQXpvckkp6AQADAgADeQADOgQ",
    "img_analit": "AgACAgIAAxkBAAIG_GmTRpUfIS2_vBBiEgmTbVbEcqy_AAKuE2sbDbugSAtg0yncoXKvAQADAgADeQADOgQ",
    "img_copy": "AgACAgIAAxkBAAIHCGmTX-JMYyDQbKnZhcaKZJDijDQkAAIEFWsbDbugSNTtaW5Zq-DHAQADAgADeQADOgQ",
    "img_design": "AgACAgIAAxkBAAIHCmmTX_VDx_e4nHnGzhFDbRhXEtsiAAIFFWsbDbugSHhwqWVHzg8pAQADAgADeQADOgQ",
    "img_managment": "AgACAgIAAxkBAAIHD2mTYH-l0U2-kPgmtLynz6D_9ENoAAIOFWsbDbugSImJmFdHgLM0AQADAgADeQADOgQ",
    "img_marketing": "AgACAgIAAxkBAAIHEmmTYKQt_gfOnwXvGCS95zHwfGmiAAIUFWsbDbugSHRY3qB5YIvGAQADAgADeQADOgQ",
    "img_video": "AgACAgIAAxkBAAIHFWmTYNFQ5wTX5gga_kGLTYqhyqoTAAIVFWsbDbugSJNA6wAB0pv6hQEAAwIAA3kAAzoE",
    "img_other": "AgACAgIAAxkBAAIHJGmTYjp2suO-P5tngaeoUfw6j2mNAAIkFWsbDbugSLm1JL7SubAJAQADAgADeQADOgQ",
    "img_kill": "AgACAgIAAxkBAAIHGGmTYRjhg1VPNkBxYN5dE8l0LBTjAAIYFWsbDbugSFbmWagOPVjdAQADAgADeQADOgQ",
    "img_gidratt": "AgACAgIAAxkBAAIG-WmTQg9VKc47CBi7rwyz1g7rlmvzAAKRE2sbDbugSIb3wlOPDq95AQADAgADeQADOgQ",
    "img_win": "AgACAgIAAxkDAAIIommq-iPKzrXdDyQC-PCjPKu7FIzqAAIcFmsbqu9YSdh-3sam4pTvAQADAgADeQADOgQ",
    "img_lose": "AgACAgIAAxkBAAIHHGmTYa1pWKvmL-3aXmA4J039lOu7AAIeFWsbDbugSH1JzvYSFXiVAQADAgADeQADOgQ",
    "img_stark": "AgACAgIAAxkBAAIHHmmTYd9iQQHNA1SJvXpuT1GG42HEAAIfFWsbDbugSLYaVhyFpZU-AQADAgADeQADOgQ",
    "img_final": "AgACAgIAAxkBAAIHIGmTYf2-91QgSxRSoODg4wc8jPbbAAIgFWsbDbugSOuMvbGbCzHAAQADAgADeQADOgQ",
}


def _fetch_from_server() -> tuple[str, str, list[int]]:
    """SSH to server, get tokens and ADMIN_IDS."""
    project_root = Path(__file__).resolve().parent.parent
    deploy_env = project_root / "deploy" / ".deploy.env"
    if not deploy_env.exists():
        raise SystemExit("deploy/.deploy.env not found")
    env = {}
    for line in deploy_env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            env[k.strip()] = v.strip()
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(env["DEPLOY_HOST"], username=env["DEPLOY_USER"], password=env["DEPLOY_PASSWORD"])

    _, o, _ = c.exec_command('grep "^BOT_TOKEN=" /opt/hydra_bot/.env 2>/dev/null | cut -d= -f2-')
    prod_token = o.read().decode().strip()
    _, o, _ = c.exec_command('grep "^BOT_TOKEN=" /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2-')
    sandbox_token = o.read().decode().strip()
    _, o, _ = c.exec_command('grep "^ADMIN_IDS=" /opt/hydra_bot_sandbox/.env 2>/dev/null | cut -d= -f2-')
    admin_raw = o.read().decode().strip()
    admin_ids = [int(x) for x in admin_raw.split(",") if x.strip().isdigit()]
    c.close()
    return prod_token, sandbox_token, admin_ids


async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-from-server", action="store_true", help="Get tokens via SSH from deploy/.deploy.env")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    for env_file in (project_root / ".env", project_root / "deploy" / ".deploy.env"):
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            break

    if args.fetch_from_server:
        print("Fetching tokens from server...")
        prod_token, sandbox_token, admin_ids = _fetch_from_server()
    else:
        prod_token = os.getenv("PROD_BOT_TOKEN") or os.getenv("BOT_TOKEN", "").strip()
        sandbox_token = os.getenv("SANDBOX_BOT_TOKEN", "").strip()
        admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

    if not prod_token or not sandbox_token:
        print("[FAIL] Need PROD_BOT_TOKEN and SANDBOX_BOT_TOKEN (or BOT_TOKEN for each env)")
        print("  Get from: grep BOT_TOKEN /opt/hydra_bot/.env and /opt/hydra_bot_sandbox/.env")
        sys.exit(1)
    if prod_token == sandbox_token:
        print("[FAIL] PROD and SANDBOX tokens must be different")
        sys.exit(1)
    if not admin_ids:
        print("[FAIL] ADMIN_IDS required (chat to receive photos for new file_id)")
        sys.exit(1)
    chat_id = admin_ids[0]
    print(f"Chat ID for upload: {chat_id}")

    from aiogram import Bot
    from aiogram.types import BufferedInputFile
    import aiohttp

    prod_bot = Bot(token=prod_token)
    sandbox_bot = Bot(token=sandbox_token)
    result: dict[str, str] = {}
    try:
        async with aiohttp.ClientSession() as session:
            for key, file_id in PROD_MEDIA.items():
                print(f"  {key}...", end=" ", flush=True)
                try:
                    file = await prod_bot.get_file(file_id)
                    url = f"https://api.telegram.org/file/bot{prod_token}/{file.file_path}"
                    async with session.get(url) as r:
                        if r.status != 200:
                            print(f"FAIL get {r.status}")
                            continue
                        data = await r.read()
                    photo = BufferedInputFile(data, filename=f"{key}.jpg")
                    msg = await sandbox_bot.send_photo(chat_id=chat_id, photo=photo, caption=f"#{key}")
                    if msg.photo:
                        result[key] = msg.photo[-1].file_id
                        print("OK")
                    else:
                        print("FAIL no photo")
                except Exception as e:
                    print(f"FAIL {e}")
    finally:
        await prod_bot.session.close()
        await sandbox_bot.session.close()

    if result:
        print(f"\n# Got {len(result)} file_ids. Paste into utils/media_ids.py → SANDBOX_MEDIA_FILE_IDS:")
        print("SANDBOX_MEDIA_FILE_IDS: dict[str, str] = {")
        for k, v in sorted(result.items()):
            print(f'    "{k}": "{v}",')
        print("}")
    else:
        print("\n[FAIL] No file_ids obtained")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
