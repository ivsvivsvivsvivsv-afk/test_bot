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
from pathlib import Path
from datetime import datetime, timezone

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from config import (
    APP_ENV,
    BOT_TOKEN,
    WEBHOOK_HOST,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
)
from db import create_pool, close_pool
from redis_client import create_redis, close_redis
from utils.content_manager import ContentManager
from utils.runtime_alerts import send_runtime_alert
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


_STARTUP_TG_TIMEOUT = 15.0  # секунд — если Telegram API недоступен, сервер всё равно поднимется


async def on_startup(app: web.Application) -> None:
    pool = await create_pool()
    redis_conn = await create_redis()

    import redis.asyncio as aioredis

    fsm_redis = aioredis.from_url(
        app[REDIS_URL_KEY], decode_responses=False
    )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = _build_dispatcher(pool, redis_conn, fsm_redis)

    try:
        # Случайная задержка — воркеры не бьют SetWebhook одновременно (Flood control)
        await asyncio.sleep(0.5 * (hash(str(id(app))) % 5))
        current_wh = await asyncio.wait_for(bot.get_webhook_info(), timeout=_STARTUP_TG_TIMEOUT)
        webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        if current_wh.url != webhook_url:
            for attempt in range(3):
                try:
                    await asyncio.wait_for(
                        bot.set_webhook(
                            url=webhook_url,
                            secret_token=WEBHOOK_SECRET,
                            drop_pending_updates=False,
                            allowed_updates=dp.resolve_used_update_types(),
                        ),
                        timeout=_STARTUP_TG_TIMEOUT,
                    )
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 0.5)
                    continue
            logger.info("Webhook set: %s", webhook_url)
        else:
            logger.info("Webhook already configured: %s", webhook_url)

        bot_info = await asyncio.wait_for(bot.get_me(), timeout=_STARTUP_TG_TIMEOUT)
        logger.info("Bot: @%s (id=%s)", bot_info.username, bot_info.id)
    except asyncio.TimeoutError:
        logger.warning("Telegram API timeout at startup — webhook may be stale, but HTTP API will work")
    except TelegramRetryAfter as e:
        logger.warning("Telegram flood at startup (retry %s s) — HTTP API will work", e.retry_after)
    except Exception as e:
        logger.warning("Telegram startup error: %s — HTTP API will work", e)

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


async def _handle_root_or_health(request: web.Request) -> web.Response:
    """Корень /: HTML для браузера, JSON иначе. /health — всегда JSON."""
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Hydra Bot API</title></head>
<body style="font-family:sans-serif;max-width:40em;margin:2em auto;padding:1em">
<h1>Hydra Bot API</h1>
<p>Это HTTP API Telegram-бота, а не веб-сайт. Используется админкой лендинга.</p>
<p><a href="/health">/health</a> — проверка состояния (JSON)</p>
</body></html>"""
        return web.Response(text=html, content_type="text/html")
    return await handle_health(request)


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
        try:
            await send_runtime_alert(
                request.app.get(BOT_KEY),
                redis_conn=None,
                key="bot_redis_health_failed",
                message=(
                    "🚨 <b>Hydra bot alert</b>\n\n"
                    "Redis health-check failed in bot process. API degraded."
                ),
            )
        except Exception:
            logger.exception("Failed to notify admins about Redis health failure")

    all_ok = checks.get("postgres") == "ok" and checks.get("redis") == "ok"
    checks["status"] = "ok" if all_ok else "degraded"
    status_code = 200 if all_ok else 503
    return web.json_response(checks, status=status_code)


async def handle_web_v1_health(_request: web.Request) -> web.Response:
    """Dedicated health endpoint for web client API."""
    return web.json_response(
        {
            "status": "ok",
            "version": "web/v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        status=200,
    )


@web.middleware
async def _sandbox_error_middleware(request: web.Request, handler):
    """In sandbox, return 500 details as JSON for debugging."""
    try:
        return await handler(request)
    except Exception as exc:
        logger.exception("Unhandled error in %s %s", request.method, request.path)
        if APP_ENV == "sandbox":
            import traceback
            return web.json_response(
                {"error": str(exc), "type": type(exc).__name__, "traceback": traceback.format_exc()},
                status=500,
            )
        raise


def create_app() -> web.Application:
    from config import REDIS_URL

    application = web.Application(middlewares=[_sandbox_error_middleware])
    application[REDIS_URL_KEY] = REDIS_URL

    application.on_startup.append(on_startup)
    application.on_shutdown.append(on_shutdown)

    from handlers.payment_webhook import handle_yookassa_webhook
    from handlers.admin_api_http import register_admin_api_routes
    from handlers.web_media_http import register_web_media_routes
    from handlers.web_flow_http import register_web_flow_routes

    application.router.add_get("/", _handle_root_or_health)
    application.router.add_get("/health", handle_health)

    # Debug: list routes (remove in prod)
    def _debug_routes(request: web.Request) -> web.Response:
        routes = []
        for r in application.router.routes():
            if hasattr(r, "resource") and hasattr(r.resource, "path"):
                path = getattr(r.resource, "path", "")
                method = getattr(r, "method", "GET")
                if path and "api/web" in str(path):
                    routes.append({"method": method, "path": path})
        return web.json_response({"web_routes": routes})

    application.router.add_get("/api/debug/routes", _debug_routes)
    application.router.add_get("/api/web/v1/health", handle_web_v1_health)
    application.router.add_post("/yookassa/webhook", handle_yookassa_webhook)
    media_dir = Path("content/web_media")
    if media_dir.exists():
        application.router.add_static("/static/media", str(media_dir), show_index=False)
    register_admin_api_routes(application)
    register_web_media_routes(application)
    register_web_flow_routes(application)

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
