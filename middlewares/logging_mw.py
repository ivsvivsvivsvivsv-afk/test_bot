from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from aiogram.types import TelegramObject


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Per-update logging with latency measurement.
    Uses stdlib logging — structlog configured only if explicitly initialized.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        user = data.get("event_from_user")
        handler_object = data.get("handler")

        handler_name = None
        if handler_object is not None:
            cb = getattr(handler_object, "callback", handler_object)
            handler_name = getattr(cb, "__name__", None)

        try:
            return await handler(event, data)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "update_failed user_id=%s handler=%s duration_ms=%d",
                getattr(user, "id", None),
                handler_name,
                elapsed_ms,
            )
            raise
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if elapsed_ms > 1000:
                logger.warning(
                    "SLOW update_processed user_id=%s type=%s handler=%s duration_ms=%d",
                    getattr(user, "id", None),
                    event.__class__.__name__,
                    handler_name,
                    elapsed_ms,
                )
            # Best-effort callback metrics for admin dashboards.
            try:
                if isinstance(event, CallbackQuery):
                    user_id = getattr(user, "id", None)
                    callback_data = event.data or ""
                    pool = data.get("pool")
                    if user_id and callback_data and pool is not None:
                        from services.quest_service import log_event

                        await log_event(
                            pool=pool,
                            user_id=int(user_id),
                            event_type="button_click",
                            event_data={"callback": callback_data},
                        )
            except Exception:
                logger.debug("button_click metric failed", exc_info=True)
