"""
HYDRA BOT — Worker (Scheduler + Рассылки)
==========================================
Запускается СТРОГО В 1 ЭКЗЕМПЛЯРЕ через systemd (hydra-worker.service).
Если запустить несколько — рассылки уйдут по N раз!

Запуск:  python worker.py
Systemd: systemctl start hydra-worker

Задачи:
  - check_idle_users     — каждые 60 сек (Redis activity keys)
  - send_daily_miniquest — ежедневно 11:00 МСК
"""

import asyncio
import logging
import signal
from types import FrameType
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db as database
import redis_client
from config import BOT_TOKEN
from services.followup_service import check_idle_users, send_daily_miniquest
from services.broadcast_service import process_due_scheduled_broadcasts
from services.notification_rule_service import process_notification_rules
from utils.content_manager import ContentManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_shutdown_event = asyncio.Event()


def _handle_signal(sig: int, _frame: Optional[FrameType] = None) -> None:
    """SIGTERM/SIGINT → устанавливаем флаг, finally-блок корректно закроет ресурсы."""
    logger.info("Received signal %s, shutting down…", signal.Signals(sig).name)
    _shutdown_event.set()


async def _run_idle_check(bot: Bot, pool, redis_conn) -> None:
    """Wrapper for APScheduler (sync callable not supported for async)."""
    try:
        await check_idle_users(bot, pool, redis_conn)
    except Exception:
        logger.exception("Idle check job failed")


async def _run_daily_miniquest(bot: Bot, pool, redis_conn) -> None:
    """Wrapper for APScheduler."""
    try:
        await send_daily_miniquest(bot, pool, redis_conn)
    except Exception:
        logger.exception("Daily miniquest job failed")


async def _run_scheduled_broadcasts(bot: Bot, pool) -> None:
    """Process pending scheduled broadcasts every minute."""
    try:
        processed = await process_due_scheduled_broadcasts(bot, pool, max_jobs=5)
        if processed:
            logger.info("Processed scheduled broadcasts: %d", processed)
    except Exception:
        logger.exception("Scheduled broadcast job failed")


async def _run_notification_rules(bot: Bot, pool) -> None:
    """Process enabled notification rules every minute."""
    try:
        processed = await process_notification_rules(bot, pool, max_rules=100)
        if processed:
            logger.info("Processed notification rules: %d", processed)
    except Exception:
        logger.exception("Notification rules job failed")


async def main() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            signal.signal(sig, _handle_signal)

    ContentManager.load("content/texts.json")

    pool = await database.create_pool(min_size=2, max_size=5)
    redis_conn = await redis_client.create_redis()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        _run_idle_check,
        "interval",
        seconds=60,
        args=[bot, pool, redis_conn],
        id="idle_check",
    )
    scheduler.add_job(
        _run_daily_miniquest,
        "cron",
        hour=11,
        minute=0,
        args=[bot, pool, redis_conn],
        id="daily_miniquest",
    )
    scheduler.add_job(
        _run_scheduled_broadcasts,
        "interval",
        seconds=60,
        args=[bot, pool],
        id="scheduled_broadcasts",
    )
    scheduler.add_job(
        _run_notification_rules,
        "interval",
        seconds=60,
        args=[bot, pool],
        id="notification_rules",
    )
    scheduler.start()
    logger.info("Worker started: idle_check every 60s, miniquest daily at 11:00 MSK")

    try:
        await _shutdown_event.wait()
    finally:
        logger.info("Worker shutting down …")
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await redis_client.close_redis(redis_conn)
        await database.close_pool(pool)
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
