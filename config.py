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
    # YooKassa
    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_return_url: str
    promo_slots_total: int = 5
    # Webhook
    webhook_host: str = ""
    webhook_path: str = "/webhook/telegram"
    # Redis (для FSM)
    redis_url: str = ""
    # PostgreSQL (для highload)
    postgres_url: str = ""


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
    
    # YooKassa
    yookassa_shop_id = os.getenv("YOOKASSA_SHOP_ID", "")
    yookassa_secret_key = os.getenv("YOOKASSA_SECRET_KEY", "")
    yookassa_return_url = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/your_bot")
    promo_slots_total = int(os.getenv("PROMO_SLOTS_TOTAL", "5"))
    
    if yookassa_shop_id and yookassa_secret_key:
        logger.info("✅ YooKassa настроена")
    else:
        logger.warning("⚠️ YooKassa не настроена (YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY)")
    
    # Webhook для Telegram (ОБЯЗАТЕЛЬНО для highload!)
    webhook_host = os.getenv("WEBHOOK_HOST", "")  # например: https://your-app.amvera.io
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook/telegram")
    
    if webhook_host:
        logger.info(f"✅ Telegram Webhook: {webhook_host}{webhook_path}")
    else:
        logger.warning("⚠️ WEBHOOK_HOST не задан — будет использоваться polling (НЕ для production!)")
    
    # Redis для FSM (ОБЯЗАТЕЛЬНО для горизонтального масштабирования)
    redis_url = os.getenv("REDIS_URL", "")  # например: redis://default:password@host:6379/0
    
    if redis_url:
        logger.info("✅ Redis FSM Storage настроен")
    else:
        logger.warning("⚠️ REDIS_URL не задан — FSM в памяти (состояния потеряются при рестарте!)")
    
    # PostgreSQL для данных (рекомендуется для highload)
    postgres_url = os.getenv("DATABASE_URL", "")  # Amvera передаёт как DATABASE_URL
    
    if postgres_url:
        logger.info("✅ PostgreSQL настроен")
        db_path = postgres_url  # Переиспользуем поле
    else:
        logger.info(f"ℹ️ Используется SQLite: {db_path}")
    
    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        admin_username=admin_username,
        db_path=db_path,
        generator_bot_url=generator_bot_url,
        workshop_url=workshop_url,
        promo_code=promo_code,
        yookassa_shop_id=yookassa_shop_id,
        yookassa_secret_key=yookassa_secret_key,
        yookassa_return_url=yookassa_return_url,
        promo_slots_total=promo_slots_total,
        webhook_host=webhook_host,
        webhook_path=webhook_path,
        redis_url=redis_url,
        postgres_url=postgres_url,
    )


# Глобальный объект настроек
settings = load_settings()

# Для обратной совместимости
BOT_TOKEN = settings.bot_token
ADMIN_IDS = settings.admin_ids
DATABASE_PATH = settings.db_path
