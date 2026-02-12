"""
Главный файл бота НЕЙРО-ЮНИТ.

HIGHLOAD АРХИТЕКТУРА:
- Telegram Webhook (не polling!) — масштабируется горизонтально
- Redis для FSM — состояния шарятся между инстансами  
- PostgreSQL для данных — выдерживает нагрузку
- aiohttp сервер — принимает webhooks от Telegram и YooKassa

Для 100K+ пользователей!
"""

import asyncio
import logging
import os
import sys
import json
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject, Update

from aiohttp import web

from config import settings
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

# Уменьшаем шум от библиотек
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# =============================================================================
# ГЛОБАЛЬНЫЕ ОБЪЕКТЫ
# =============================================================================

bot: Bot = None
db: Database = None
dp: Dispatcher = None


# =============================================================================
# MIDDLEWARE ДЛЯ INJECTION DATABASE
# =============================================================================

class DatabaseMiddleware:
    """Middleware для инъекции Database в обработчики."""
    
    def __init__(self, database: Database):
        self.db = database
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["db"] = self.db
        return await handler(event, data)


# =============================================================================
# FSM STORAGE (Redis или Memory)
# =============================================================================

def get_fsm_storage():
    """
    Выбор FSM storage в зависимости от конфигурации.
    
    Для production ОБЯЗАТЕЛЬНО используйте Redis!
    """
    redis_client = None
    
    if settings.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            from redis.asyncio import Redis
            
            redis_client = Redis.from_url(settings.redis_url)
            
            # Передаём Redis client в promo для distributed locks
            from handlers.promo import set_redis_client
            set_redis_client(redis_client)
            
            logger.info("✅ Using Redis FSM Storage + Distributed Locks")
            return RedisStorage(redis=redis_client), redis_client
        except ImportError:
            logger.error("❌ redis package not installed! Run: pip install redis")
            logger.warning("⚠️ Falling back to MemoryStorage")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.warning("⚠️ Falling back to MemoryStorage")
    
    from aiogram.fsm.storage.memory import MemoryStorage
    logger.warning("⚠️ Using MemoryStorage (NOT for production!)")
    logger.warning("⚠️ Distributed locks DISABLED - promo may have race conditions!")
    return MemoryStorage(), None


# =============================================================================
# AIOHTTP HANDLERS
# =============================================================================

async def handle_health(request: web.Request) -> web.Response:
    """Health check для Amvera и мониторинга."""
    return web.json_response({
        "status": "ok",
        "service": "neuro-unit-bot",
        "mode": "webhook" if settings.webhook_host else "polling"
    })


async def handle_yookassa_webhook(request: web.Request) -> web.Response:
    """
    Webhook endpoint для YooKassa.
    POST /webhook/yookassa
    """
    global bot, db
    
    try:
        body = await request.text()
        logger.info(f"YooKassa webhook: {body[:500]}")
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from YooKassa: {e}")
            return web.json_response({"error": "Invalid JSON"}, status=400)
        
        event_type = data.get("event")
        
        if event_type == "payment.succeeded":
            payment_obj = data.get("object", {})
            payment_id = payment_obj.get("id")
            metadata = payment_obj.get("metadata", {})
            user_id_str = metadata.get("user_id")
            
            logger.info(f"Payment succeeded: id={payment_id}, user_id={user_id_str}")
            
            if user_id_str and payment_id:
                try:
                    user_id = int(user_id_str)
                    from handlers.promo import confirm_promo_payment
                    await confirm_promo_payment(bot, db, user_id, payment_id)
                    logger.info(f"Payment confirmed for user {user_id}")
                except ValueError:
                    logger.error(f"Invalid user_id: {user_id_str}")
                except Exception as e:
                    logger.exception(f"Error confirming payment: {e}")
        
        # Всегда 200, иначе YooKassa повторяет
        return web.json_response({"status": "ok"})
        
    except Exception as e:
        logger.exception(f"YooKassa webhook error: {e}")
        return web.json_response({"status": "error"})


# =============================================================================
# TELEGRAM WEBHOOK HANDLER
# =============================================================================

async def handle_telegram_webhook(request: web.Request) -> web.Response:
    """
    Обработка Telegram webhook.
    POST /webhook/telegram
    """
    global bot, dp
    
    try:
        # Парсим Update от Telegram
        data = await request.json()
        update = Update(**data)
        
        # Передаём в диспетчер
        await dp.feed_update(bot=bot, update=update)
        
        return web.Response(status=200)
        
    except Exception as e:
        logger.exception(f"Telegram webhook error: {e}")
        return web.Response(status=500)


# =============================================================================
# STARTUP / SHUTDOWN
# =============================================================================

async def on_startup(app: web.Application):
    """Вызывается при старте приложения."""
    global bot, db, dp
    
    logger.info("=" * 60)
    logger.info("Starting NEURO-UNIT Bot (HIGHLOAD MODE)")
    logger.info("=" * 60)
    
    # Инициализируем базу данных
    db = Database(settings.db_path)
    await db.init()
    logger.info("Database initialized")
    
    # Создаём бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # FSM Storage (+ Redis client for distributed locks)
    storage, redis_client = get_fsm_storage()
    dp = Dispatcher(storage=storage)
    
    # Store redis client in app for cleanup
    app["redis_client"] = redis_client
    
    # Middleware
    dp.update.middleware(DatabaseMiddleware(db))
    
    # Роутеры
    from handlers.start import router as start_router
    from handlers.quest import router as quest_router
    from handlers.contacts import router as contacts_router
    from handlers.arena import router as arena_router
    from handlers.promo import router as promo_router
    
    dp.include_router(start_router)
    dp.include_router(quest_router)
    dp.include_router(contacts_router)
    dp.include_router(arena_router)
    dp.include_router(promo_router)
    
    logger.info("Routers registered")
    
    # Информация о боте
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username} (ID: {bot_info.id})")
    
    # Устанавливаем webhook для Telegram
    if settings.webhook_host:
        webhook_url = f"{settings.webhook_host}{settings.webhook_path}"
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        )
        logger.info(f"✅ Telegram Webhook set: {webhook_url}")
    else:
        logger.warning("⚠️ WEBHOOK_HOST not set, webhook not configured")
    
    # Сохраняем в app для доступа из handlers
    app["bot"] = bot
    app["db"] = db
    app["dp"] = dp


async def on_shutdown(app: web.Application):
    """Вызывается при остановке приложения."""
    global bot, db
    
    logger.info("Shutting down...")
    
    if bot:
        # Удаляем webhook
        if settings.webhook_host:
            await bot.delete_webhook()
            logger.info("Webhook deleted")
        await bot.session.close()
    
    if db:
        await db.close()
    
    # Закрываем Redis
    redis_client = app.get("redis_client")
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")
    
    logger.info("Bot stopped")


# =============================================================================
# СОЗДАНИЕ ПРИЛОЖЕНИЯ
# =============================================================================

def create_app() -> web.Application:
    """Создание aiohttp приложения."""
    app = web.Application()
    
    # Lifecycle hooks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Роуты
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/webhook/yookassa", handle_yookassa_webhook)
    app.router.add_post(settings.webhook_path, handle_telegram_webhook)
    
    logger.info(f"Routes: /, /health, /webhook/yookassa, {settings.webhook_path}")
    
    return app


# =============================================================================
# FALLBACK: POLLING MODE (только для локальной разработки!)
# =============================================================================

async def run_polling():
    """
    Запуск в режиме polling.
    ТОЛЬКО для локальной разработки, НЕ для production!
    """
    global bot, db, dp
    
    logger.warning("=" * 60)
    logger.warning("⚠️  POLLING MODE — NOT FOR PRODUCTION!")
    logger.warning("⚠️  Set WEBHOOK_HOST for production deployment")
    logger.warning("=" * 60)
    
    # Инициализация
    db = Database(settings.db_path)
    await db.init()
    
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage, redis_client = get_fsm_storage()
    dp = Dispatcher(storage=storage)
    dp.update.middleware(DatabaseMiddleware(db))
    
    # Роутеры
    from handlers.start import router as start_router
    from handlers.quest import router as quest_router
    from handlers.contacts import router as contacts_router
    from handlers.arena import router as arena_router
    from handlers.promo import router as promo_router
    
    dp.include_router(start_router)
    dp.include_router(quest_router)
    dp.include_router(contacts_router)
    dp.include_router(arena_router)
    dp.include_router(promo_router)
    
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username}")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()
        if redis_client:
            await redis_client.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Точка входа."""
    
    if settings.webhook_host:
        # === PRODUCTION: Webhook mode ===
        app = create_app()
        
        port = int(os.getenv("PORT", "8080"))
        host = os.getenv("HOST", "0.0.0.0")
        
        logger.info(f"Starting webhook server on {host}:{port}")
        web.run_app(app, host=host, port=port, print=None)
    else:
        # === DEVELOPMENT: Polling mode ===
        asyncio.run(run_polling())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
