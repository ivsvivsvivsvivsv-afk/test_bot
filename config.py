"""
Конфигурация бота «Гидра Сингулярности» — Production MVP
=========================================================
Все параметры загружаются из .env через python-dotenv.
Модуль импортируется как в bot.py (Gunicorn), так и в worker.py (scheduler).
"""

import os
import sys
import re
import logging
from typing import List
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ── Вспомогательные функции ──────────────────────────────────


def _require(name: str) -> str:
    """Обязательная переменная — без неё бот не стартует."""
    value = os.getenv(name, "").strip()
    if not value:
        logger.critical("MISSING REQUIRED ENV: %s", name)
        sys.exit(1)
    return value


def _int_env(name: str, default: str) -> int:
    """Безопасное чтение int из env с внятной ошибкой вместо голого ValueError."""
    raw = os.getenv(name, default).strip()
    try:
        return int(raw)
    except ValueError:
        logger.critical("ENV %s must be integer, got: %r", name, raw)
        sys.exit(1)


def _parse_admin_ids(raw: str) -> List[int]:
    ids: List[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.append(int(chunk))
    return ids


# ── Telegram ─────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")

# Telegram выдаёт bot-ID от 8 до 13+ цифр; не ограничиваем сверху жёстко
if not re.match(r"^\d{6,15}:[A-Za-z0-9_-]{30,50}$", BOT_TOKEN):
    logger.critical("BOT_TOKEN has invalid format: %s...", BOT_TOKEN[:15])
    sys.exit(1)

ADMIN_IDS: List[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
if not ADMIN_IDS:
    logger.warning("ADMIN_IDS is empty — admin commands will be unavailable")

ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "fimadima13")

# ── Webhook ──────────────────────────────────────────────────
WEBHOOK_HOST: str = _require("WEBHOOK_HOST")
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook/bot")
WEBHOOK_PORT: int = _int_env("WEBHOOK_PORT", "8443")
WEBHOOK_SECRET: str = _require("WEBHOOK_SECRET")

# ── PostgreSQL ───────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = _int_env("DB_PORT", "5432")
DB_NAME: str = os.getenv("DB_NAME", "hydra_bot")
DB_USER: str = os.getenv("DB_USER", "hydra")
DB_PASSWORD: str = _require("DB_PASSWORD")

# quote_plus экранирует спецсимволы (@, #, /, :) в пароле и username
DB_DSN: str = (
    f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# 4 Gunicorn workers × 10 = 40  <  PG default max_connections (100)
DB_POOL_MIN: int = _int_env("DB_POOL_MIN", "2")
DB_POOL_MAX: int = _int_env("DB_POOL_MAX", "10")

# ── Redis ────────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ── Deployment target / API security ────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "production").strip().lower()  # production|sandbox
APP_INSTANCE: str = os.getenv("APP_INSTANCE", "hydra-prod").strip()
ADMIN_API_SECRET: str = os.getenv("ADMIN_API_SECRET", "").strip()
SITE_WEBHOOK_SECRET: str = os.getenv("SITE_WEBHOOK_SECRET", "").strip()

# ── YooKassa ─────────────────────────────────────────────────
YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_RETURN_URL: str = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/neurounit_bot")

# ── Внешние ссылки ───────────────────────────────────────────
GENERATOR_BOT_URL: str = os.getenv("GENERATOR_BOT_URL", "https://t.me/video_generator_bot")
WORKSHOP_URL: str = os.getenv("WORKSHOP_URL", "https://example.com/workshop")

# ── Призы ────────────────────────────────────────────────────
PRIZE_CONTACT: str = f"@{ADMIN_USERNAME}"
PROMO_CODE: str = os.getenv("PROMO_CODE", "HYDRA50")

# ── Дожим (Follow-up) ───────────────────────────────────────
FOLLOWUP_IDLE_MINUTES: int = _int_env("FOLLOWUP_IDLE_MINUTES", "5")
FOLLOWUP_DAYS: int = _int_env("FOLLOWUP_DAYS", "5")

# ── Диагностика при импорте ──────────────────────────────────
logger.info(
    "Config loaded: bot_id=%s, admins=%s, webhook=%s%s, db=%s@%s:%d/%s",
    BOT_TOKEN.split(":")[0],
    ADMIN_IDS,
    WEBHOOK_HOST,
    WEBHOOK_PATH,
    DB_USER,
    DB_HOST,
    DB_PORT,
    DB_NAME,
)
