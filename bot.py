"""
Hydra Singularity Bot — production entry point.

Launch modes
============
Webhook (production):
    gunicorn bot:app --worker-class aiohttp.GunicornWebWorker --workers 4

Polling (dev only):
    python bot.py

Architecture rules
==================
1. NO APScheduler here — scheduled jobs live in worker.py.
2. NO bot.delete_webhook() in on_shutdown — graceful reload must not
   kill the webhook for other workers.
3. get_webhook_info() before set_webhook() — avoids redundant API calls
   when 4 workers start simultaneously.
4. secret_token on webhook — Telegram verifies X-Telegram-Bot-Api-Secret-Token.
5. ContentManager.load() runs once per worker at import time.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from config import (
    BOT_TOKEN,
    WEBHOOK_HOST,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
)
from db import create_pool, close_pool
from redis_client import create_redis, close_redis
from utils.content_manager import ContentManager
from middlewares.db_middleware import DBMiddleware
from middlewares.logging_mw import LoggingMiddleware

# ── Logging ─────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── aiohttp app keys (avoid stringly-typed state) ───────────

REDIS_URL_KEY: web.AppKey[str] = web.AppKey("redis_url", str)
BOT_KEY: web.AppKey[Bot] = web.AppKey("bot", Bot)
DP_KEY: web.AppKey[Dispatcher] = web.AppKey("dp", Dispatcher)
POOL_KEY: web.AppKey[object] = web.AppKey("pool", object)
REDIS_CONN_KEY: web.AppKey[object] = web.AppKey("redis_conn", object)
FSM_REDIS_KEY: web.AppKey[object] = web.AppKey("fsm_redis", object)

# ── Load content once per worker ────────────────────────────

ContentManager.load("content/texts.json")

# ── Shared dispatcher builder ────────────────────────────────


def _build_dispatcher(
    pool, redis_conn, fsm_redis,
) -> Dispatcher:
    """Shared dispatcher construction for both webhook and polling modes."""
    storage = RedisStorage(redis=fsm_redis)
    dp = Dispatcher(storage=storage)

    from middlewares import ActivityMiddleware, ThrottleMiddleware

    dp.update.middleware(DBMiddleware(pool, redis_conn))
    dp.update.middleware(ActivityMiddleware())
    dp.update.middleware(ThrottleMiddleware())
    dp.update.middleware(LoggingMiddleware())

    from handlers.admin import router as admin_router
    from handlers.start import router as start_router
    from handlers.quest import router as quest_router

    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(quest_router)

    _optional_routers = [
        ("handlers.contacts", "contacts"),
        ("handlers.arena", "arena"),
        ("handlers.upsell", "upsell"),
        ("handlers.followup", "followup"),
    ]
    for module_path, name in _optional_routers:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            dp.include_router(mod.router)
        except (ImportError, AttributeError):
            logger.warning("%s router not available", name)

    return dp


# ── Factory ─────────────────────────────────────────────────


async def on_startup(app: web.Application) -> None:
    pool = await create_pool()
    redis_conn = await create_redis()

    import redis.asyncio as aioredis

    fsm_redis = aioredis.from_url(
        app[REDIS_URL_KEY], decode_responses=False
    )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = _build_dispatcher(pool, redis_conn, fsm_redis)

    current_wh = await bot.get_webhook_info()
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    if current_wh.url != webhook_url:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
            allowed_updates=dp.resolve_used_update_types(),
        )
        logger.info("Webhook set: %s", webhook_url)
    else:
        logger.info("Webhook already configured: %s", webhook_url)

    bot_info = await bot.get_me()
    logger.info("Bot: @%s (id=%s)", bot_info.username, bot_info.id)

    app[BOT_KEY] = bot
    app[DP_KEY] = dp
    app[POOL_KEY] = pool
    app[REDIS_CONN_KEY] = redis_conn
    app[FSM_REDIS_KEY] = fsm_redis

    handler = SimpleRequestHandler(dp, bot, secret_token=WEBHOOK_SECRET)
    handler.register(app, path=WEBHOOK_PATH)

async def on_shutdown(app: web.Application) -> None:
    logger.info("Shutting down …")

    bot: Bot | None = app.get(BOT_KEY)
    if bot:
        # Do NOT delete_webhook — other workers still need it
        await bot.session.close()

    fsm_redis = app.get(FSM_REDIS_KEY)
    if fsm_redis:
        await fsm_redis.aclose()

    await close_redis()
    await close_pool()
    logger.info("Shutdown complete")


async def handle_health(request: web.Request) -> web.Response:
    checks: dict = {"service": "hydra-bot"}
    try:
        pool = request.app.get(POOL_KEY)
        if pool:
            async with pool.acquire(timeout=2) as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        else:
            checks["postgres"] = "not_initialized"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    try:
        rc = request.app.get(REDIS_CONN_KEY)
        if rc:
            await rc.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_initialized"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = checks.get("postgres") == "ok" and checks.get("redis") == "ok"
    checks["status"] = "ok" if all_ok else "degraded"
    status_code = 200 if all_ok else 503
    return web.json_response(checks, status=status_code)


def create_app() -> web.Application:
    from config import REDIS_URL

    application = web.Application()
    application[REDIS_URL_KEY] = REDIS_URL

    application.on_startup.append(on_startup)
    application.on_shutdown.append(on_shutdown)

    from handlers.payment_webhook import handle_yookassa_webhook
    from handlers.admin_api_http import register_admin_api_routes

    application.router.add_get("/", handle_health)
    application.router.add_get("/health", handle_health)
    application.router.add_post("/yookassa/webhook", handle_yookassa_webhook)
    register_admin_api_routes(application)

    return application


# Gunicorn entry: ``gunicorn bot:app …``
app = create_app()


# ── Polling fallback (dev only) ─────────────────────────────


async def run_polling() -> None:
    logger.warning("=" * 50)
    logger.warning("POLLING MODE — NOT FOR PRODUCTION")
    logger.warning("=" * 50)

    from config import REDIS_URL
    import redis.asyncio as aioredis

    pool = await create_pool()
    redis_conn = await create_redis()
    fsm_redis = aioredis.from_url(REDIS_URL, decode_responses=False)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = _build_dispatcher(pool, redis_conn, fsm_redis)

    bot_info = await bot.get_me()
    logger.info("Bot: @%s", bot_info.username)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await fsm_redis.aclose()
        await close_redis()
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)
