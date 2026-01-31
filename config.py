"""
Конфигурация бота НЕЙРО-ЮНИТ
============================
Загрузка переменных окружения с диагностикой и валидацией.
"""

import os
import sys
import logging
import re
from dataclasses import dataclass
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# НАСТРОЙКИ (dataclass для type hints)
# =============================================================================

@dataclass
class Settings:
    """Настройки приложения."""
    bot_token: str
    admin_ids: List[int]
    admin_username: str
    db_path: str
    generator_bot_url: str
    workshop_url: str
    promo_code: str


def validate_token(token: str) -> bool:
    """Проверка формата токена Telegram."""
    if not token:
        return False
    # Формат: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    pattern = r'^\d{8,10}:[A-Za-z0-9_-]{35,40}$'
    return bool(re.match(pattern, token))


def load_settings() -> Settings:
    """Загрузка и валидация настроек."""
    
    # BOT_TOKEN
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    
    if not bot_token:
        logger.critical("❌ BOT_TOKEN не задан!")
        logger.critical("   Добавьте BOT_TOKEN в переменные окружения Amvera")
        sys.exit(1)
    
    if not validate_token(bot_token):
        logger.critical(f"❌ BOT_TOKEN имеет неверный формат!")
        logger.critical(f"   Текущее значение: {bot_token[:20]}...")
        sys.exit(1)
    
    bot_id = bot_token.split(":")[0]
    logger.info(f"✅ BOT_TOKEN загружен (ID: {bot_id})")
    
    # ADMIN_IDS
    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    admin_ids: List[int] = []
    
    if admin_ids_raw:
        for item in admin_ids_raw.split(","):
            item = item.strip()
            if item.isdigit():
                admin_ids.append(int(item))
            else:
                logger.warning(f"⚠️ Невалидный ADMIN_ID: '{item}'")
    
    if admin_ids:
        logger.info(f"✅ ADMIN_IDS: {admin_ids}")
    else:
        logger.warning("⚠️ ADMIN_IDS не заданы")
    
    # ADMIN_USERNAME
    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
    
    # DATABASE_PATH
    # На Amvera volume монтируется в /data
    data_dir = os.getenv("DATA_DIR", "/data")
    if not Path(data_dir).exists():
        data_dir = "."  # fallback для локальной разработки
    
    db_path = os.getenv("DATABASE_PATH", os.path.join(data_dir, "bot.db"))
    logger.info(f"✅ Database: {db_path}")
    
    # URLs
    generator_bot_url = os.getenv("GENERATOR_BOT_URL", "https://t.me/video_generator_bot")
    workshop_url = os.getenv("WORKSHOP_URL", "https://example.com/workshop")
    promo_code = os.getenv("PROMO_CODE", "NEUROUNIT50")
    
    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        admin_username=admin_username,
        db_path=db_path,
        generator_bot_url=generator_bot_url,
        workshop_url=workshop_url,
        promo_code=promo_code,
    )


# Глобальный объект настроек
settings = load_settings()

# Для обратной совместимости
BOT_TOKEN = settings.bot_token
ADMIN_IDS = settings.admin_ids
DATABASE_PATH = settings.db_path
