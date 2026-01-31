"""
Главный файл бота НЕЙРО-ЮНИТ.

Особенности:
- Правильный порядок регистрации роутеров (важно!)
- Dependency injection для Database
- Graceful shutdown
- Совместимость с Amvera (long polling)
"""

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject

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

logger = logging.getLogger(__name__)


# =============================================================================
# MIDDLEWARE ДЛЯ INJECTION DATABASE
# =============================================================================

class DatabaseMiddleware:
    """
    Middleware для инъекции Database в обработчики.
    Позволяет получать db через параметр функции.
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["db"] = self.db
        return await handler(event, data)


# =============================================================================
# ЗАПУСК БОТА
# =============================================================================

async def main():
    """Главная функция запуска бота."""
    
    logger.info("=" * 60)
    logger.info("Starting NEURO-UNIT Bot")
    logger.info("=" * 60)
    
    # Проверяем токен
    if not settings.bot_token:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)
    
    logger.info(f"Bot token: {settings.bot_token[:10]}...{settings.bot_token[-5:]}")
    logger.info(f"Admin IDs: {settings.admin_ids}")
    logger.info(f"Database path: {settings.db_path}")
    
    # Инициализируем базу данных
    db = Database(settings.db_path)
    await db.init()
    logger.info("Database initialized")
    
    # Создаём бота и диспетчер
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Используем MemoryStorage для FSM (для production лучше Redis)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем middleware для Database
    dp.update.middleware(DatabaseMiddleware(db))
    
    # ==========================================================================
    # ВАЖНО: ПОРЯДОК РЕГИСТРАЦИИ РОУТЕРОВ!
    # 
    # Роутеры с конкретными фильтрами должны быть ПЕРЕД роутерами с catch-all.
    # В нашем случае contacts.py и arena.py используют FSM состояния,
    # поэтому их message handlers НЕ являются catch-all.
    # ==========================================================================
    
    # Импортируем роутеры
    from handlers.start import router as start_router
    from handlers.quest import router as quest_router
    from handlers.contacts import router as contacts_router
    from handlers.arena import router as arena_router
    
    # Регистрируем роутеры в правильном порядке
    # 1. start - команды /start, /help, /restart, /status
    # 2. quest - квест (класс, оружие, раунды)
    # 3. contacts - сбор контактов (FSM-based message handlers)
    # 4. arena - арена (FSM-based)
    
    dp.include_router(start_router)
    dp.include_router(quest_router)
    dp.include_router(contacts_router)
    dp.include_router(arena_router)
    
    logger.info("Routers registered: start, quest, contacts, arena")
    
    # Получаем информацию о боте
    try:
        bot_info = await bot.get_me()
        logger.info(f"Bot info: @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        sys.exit(1)
    
    # Запускаем long polling
    logger.info("Starting long polling...")
    
    try:
        # Удаляем webhook если был
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, pending updates dropped")
        
        # Запускаем polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=True
        )
    except Exception as e:
        logger.error(f"Polling error: {e}")
        raise
    finally:
        # Закрываем соединения
        logger.info("Shutting down...")
        await db.close()
        await bot.session.close()
        logger.info("Bot stopped")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
