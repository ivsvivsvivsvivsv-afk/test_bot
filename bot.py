import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import start, quest, arena, contacts


async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)

    # ✅ ВАЖНО: убираем webhook, иначе polling (getUpdates) не работает
    await bot.delete_webhook(drop_pending_updates=True)

    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(quest.router)
    dp.include_router(arena.router)
    dp.include_router(contacts.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


