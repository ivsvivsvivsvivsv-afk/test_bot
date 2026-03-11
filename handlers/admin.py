"""
Admin commands: /stats, /slots, /reset_user, /reset_all, /broadcast, /export_leads.

Policy (STAGE_8):
- Notifications: only leads + payments (no notify_new_user, notify_quest_completed)
- Analytics: only leads and payment statuses (full funnel in external analytics)
"""

from __future__ import annotations

import csv
import io
import logging
import asyncpg
from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, StateFilter
from aiogram.types import BufferedInputFile, Message
from redis.asyncio import Redis

from config import ADMIN_IDS
from services.broadcast_service import broadcast
from services.payment_service import get_remaining_slots
from utils.config_db import get_config
from utils.content_manager import ContentManager

logger = logging.getLogger(__name__)

router = Router(name="admin")


# ── Admin filter ──────────────────────────────────────────────


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message) -> bool:
        return event.from_user is not None and event.from_user.id in ADMIN_IDS


# ── /stats — Лиды и статусы оплат ────────────────────────────


@router.message(Command("stats"), F.text, StateFilter("*"), AdminFilter())
async def cmd_stats(
    message: Message,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Лиды и статусы оплат. Полная воронка — во внешней аналитике."""
    async with pool.acquire() as conn:
        leads_quest = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE workshop_registered = TRUE"
        ) or 0
        leads_arena = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE arena_registered = TRUE"
        ) or 0
        leads_total = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM (
                SELECT user_id FROM users WHERE workshop_registered = TRUE
                UNION
                SELECT user_id FROM users WHERE arena_registered = TRUE
            ) t
            """
        ) or 0

        pay = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'succeeded')::int as succeeded,
                COUNT(*) FILTER (WHERE status = 'pending')::int as pending,
                COUNT(*) FILTER (WHERE status = 'canceled')::int as canceled,
                COUNT(*) FILTER (WHERE status = 'refunded')::int as refunded,
                COALESCE(SUM(amount) FILTER (WHERE status = 'succeeded'), 0)::float as revenue
            FROM payments WHERE offer_type = 'business_review'
            """
        )

    remaining = await get_remaining_slots(pool, redis_conn)
    cfg = await get_config(pool)
    total_slots = int(cfg.get("upsell_total_slots", "10"))

    text = (
        "📊 <b>ЛИДЫ И ОПЛАТЫ</b>\n\n"
        "📱 <b>Лиды (телефон/регистрация):</b>\n"
        f"   Квест: {leads_quest}\n"
        f"   Арена: {leads_arena}\n"
        f"   Всего: {leads_total}\n\n"
        "💳 <b>Оплаты:</b>\n"
        f"   Успешно: {pay['succeeded']}\n"
        f"   В ожидании: {pay['pending']}\n"
        f"   Отменено: {pay['canceled']}\n"
        f"   Возвращено: {pay['refunded']}\n\n"
        f"💰 Выручка: {pay['revenue']:,.0f} ₽\n"
        f"🪑 Мест на разбор: {remaining}/{total_slots}"
    )
    await message.answer(text)


# ── /slots ────────────────────────────────────────────────────


@router.message(Command("slots"), F.text, StateFilter("*"), AdminFilter())
async def cmd_slots(
    message: Message,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Оставшиеся места на upsell."""
    remaining = await get_remaining_slots(pool, redis_conn)
    cfg = await get_config(pool)
    total = int(cfg.get("upsell_total_slots", "10"))
    await message.answer(f"🪑 Мест на разбор: {remaining}/{total}")


# ── /reset_user ───────────────────────────────────────────────


@router.message(Command("reset_user"), F.text, StateFilter("*"), AdminFilter())
async def cmd_reset_user(
    message: Message,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Сброс прогресса конкретного игрока. Контакты и платежи НЕ трогаем."""
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(ContentManager.get_raw("reset_user_usage"))
        return

    target_id = int(parts[1])

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
            target_id,
        )

    if not row:
        await message.answer(f"❌ Пользователь {target_id} не найден")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users SET
                quest_state = 'start',
                quest_completed = FALSE,
                quest_completed_at = NULL,
                player_class = NULL,
                weapon = NULL,
                score = 0,
                round_number = 0,
                current_statement_hash = NULL,
                current_is_truth = NULL,
                followup_stage = 0,
                followup_completed = FALSE,
                upsell_shown = FALSE
            WHERE user_id = $1
            """,
            target_id,
        )

    deleted = 0
    batch: list[str] = []
    async for key in redis_conn.scan_iter(match=f"fsm:*:{target_id}:*", count=100):
        batch.append(key)
    if batch:
        deleted = await redis_conn.delete(*batch)

    un = f"@{row['username']}" if row["username"] else "—"
    await message.answer(
        f"✅ Прогресс сброшен для {row['first_name']} ({un}).\n"
        f"📱 Контакты и платежи — не тронуты.\n"
        f"🗑 FSM ключей удалено: {deleted}"
    )


# ── /reset_all ────────────────────────────────────────────────


@router.message(Command("reset_all"), F.text, StateFilter("*"), AdminFilter())
async def cmd_reset_all(
    message: Message,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> None:
    """Сброс прогресса ВСЕХ. Контакты и платежи сохраняются."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE users SET
                quest_state = 'start',
                quest_completed = FALSE,
                quest_completed_at = NULL,
                player_class = NULL,
                weapon = NULL,
                score = 0,
                round_number = 0,
                current_statement_hash = NULL,
                current_is_truth = NULL,
                followup_stage = 0,
                followup_completed = FALSE,
                upsell_shown = FALSE
            WHERE quest_completed = TRUE OR quest_state != 'start'
            """
        )

    deleted = 0
    batch: list[str] = []
    async for key in redis_conn.scan_iter(match="fsm:*", count=500):
        batch.append(key)
        if len(batch) >= 500:
            deleted += await redis_conn.delete(*batch)
            batch.clear()
    if batch:
        deleted += await redis_conn.delete(*batch)

    affected = result.split()[-1] if result else "0"
    await message.answer(
        f"✅ Прогресс сброшен для {affected} пользователей.\n"
        f"🗑 Удалено FSM-ключей: {deleted}\n"
        f"📱 Контакты, платежи — не тронуты."
    )


# ── /broadcast ────────────────────────────────────────────────


@router.message(Command("broadcast"), F.text, StateFilter("*"), AdminFilter())
async def cmd_broadcast(
    message: Message,
    pool: asyncpg.Pool,
) -> None:
    """Рассылка: /broadcast <текст>. Запускается как фоновая задача."""
    text = message.text.replace("/broadcast ", "", 1).strip()
    if not text:
        await message.answer("Использование: /broadcast <текст>")
        return

    import asyncio

    async def _do_broadcast():
        try:
            result = await broadcast(message.bot, pool, text)
            try:
                await message.answer(
                    f"✅ Рассылка завершена: отправлено {result['sent']}, ошибок {result['failed']}"
                )
            except Exception:
                logger.warning("Could not send broadcast result to admin")
        except Exception:
            logger.exception("Broadcast failed")
            try:
                await message.answer("❌ Рассылка завершилась с ошибкой. Проверьте логи.")
            except Exception:
                pass

    asyncio.create_task(_do_broadcast())
    await message.answer("📤 Рассылка запущена в фоне. Результат придёт по завершении.")


# ── /export_leads ────────────────────────────────────────────


@router.message(Command("export_leads"), F.text, StateFilter("*"), AdminFilter())
async def cmd_export_leads(
    message: Message,
    pool: asyncpg.Pool,
) -> None:
    """Экспорт лидов в CSV."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, username, first_name, phone, email,
                   player_class, weapon, score, quest_completed, workshop_registered,
                   arena_registered, arena_q1_experience, arena_q2_tools, arena_q3_goal,
                   created_at
            FROM users
            WHERE phone IS NOT NULL OR arena_registered = TRUE
            ORDER BY created_at DESC
            """
        )

    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(
        [
            "user_id", "username", "first_name", "phone", "email",
            "class", "weapon", "score", "quest_completed", "workshop",
            "arena", "arena_exp", "arena_tools", "arena_goal", "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["user_id"],
                r["username"] or "",
                r["first_name"] or "",
                r["phone"] or "",
                r["email"] or "",
                r["player_class"] or "",
                r["weapon"] or "",
                r["score"] or 0,
                r["quest_completed"],
                r["workshop_registered"],
                r["arena_registered"],
                r.get("arena_q1_experience") or "",
                r.get("arena_q2_tools") or "",
                r.get("arena_q3_goal") or "",
                r["created_at"].isoformat() if r["created_at"] else "",
            ]
        )

    buf.seek(0)
    file = BufferedInputFile(buf.getvalue().encode("utf-8-sig"), filename="leads.csv")
    await message.answer_document(file, caption=f"📊 Экспорт: {len(rows)} лидов")
