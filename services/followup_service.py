"""
Followup service — idle reminders and 5-day miniquests.

Called by worker.py (APScheduler). Uses MGET for batch activity check.
Медиа: только file_id из utils/media_ids (никаких файлов на диске).
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from redis.asyncio import Redis

from config import FOLLOWUP_IDLE_MINUTES
from utils.content_manager import ContentManager
from utils.media_ids import get_miniquest_file_id
from utils.statements import get_statement_for_miniquest

logger = logging.getLogger(__name__)

ACTIVITY_TTL = FOLLOWUP_IDLE_MINUTES * 60
BROADCAST_DELAY = 0.05


async def check_idle_users(
    bot: Bot,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> int:
    """
    Find users stuck in quest (>5 min idle), send one-time reminder.
    Uses MGET (not N×exists). Sets followup_stage=-1 before sending.
    Returns count of reminders sent.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id FROM users
            WHERE quest_completed = FALSE
              AND quest_state NOT IN ('start', 'completed')
              AND followup_stage = 0
              AND is_blocked = FALSE
            """
        )

    if not rows:
        return 0

    keys = [f"activity:{r['user_id']}" for r in rows]
    statuses = await redis_conn.mget(keys)
    idle = [r for r, s in zip(rows, statuses) if s is None]

    sent = 0
    for row in idle:
        user_id = row["user_id"]
        try:
            await pool.execute(
                "UPDATE users SET followup_stage = -1 WHERE user_id = $1",
                user_id,
            )
            await bot.send_message(
                user_id,
                ContentManager.get_raw("idle_reminder"),
            )
            sent += 1
            await asyncio.sleep(BROADCAST_DELAY)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            await pool.execute(
                "UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                user_id,
            )
            logger.info("User %s blocked bot, marked is_blocked", user_id)
        except Exception:
            logger.exception("Idle reminder failed for user %s", user_id)
            await pool.execute(
                "UPDATE users SET followup_stage = 0 WHERE user_id = $1",
                user_id,
            )

    if sent:
        logger.info("Idle reminders sent: %d/%d", sent, len(idle))
    return sent


async def send_daily_miniquest(
    bot: Bot,
    pool: asyncpg.Pool,
    redis_conn: Redis,
) -> int:
    """
    Send day N miniquest to users: quest_completed, !workshop_registered,
    followup_stage 0-4. Runs once/day at 11:00 MSK.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, followup_stage, weapon
            FROM users
            WHERE quest_completed = TRUE
              AND workshop_registered = FALSE
              AND followup_stage BETWEEN 0 AND 4
              AND followup_completed = FALSE
              AND is_blocked = FALSE
              AND COALESCE(quest_completed_at, created_at) <= NOW() - INTERVAL '1 day' * (followup_stage + 1)
            """
        )

    if not rows:
        logger.debug("No users for daily miniquest")
        return 0

    from keyboards.inline import get_miniquest_answer_keyboard

    sent = 0
    for row in rows:
        user_id = row["user_id"]
        stage = row["followup_stage"]
        day = stage + 1
        weapon = row["weapon"] or "other"

        # Mark BEFORE sending (ТЗ: при ошибке не слать повторно)
        try:
            sql = (
                "UPDATE users SET followup_stage = $1, followup_completed = $2 WHERE user_id = $3"
            )
            await pool.execute(sql, day, day >= 5, user_id)
        except Exception:
            logger.exception("Failed to pre-update followup_stage for user %s", user_id)
            continue

        try:
            narrative = ContentManager.get_raw(f"miniquest_day{day}")
        except KeyError:
            narrative = f"🐉 Миниквест дня {day}"

        fid = get_miniquest_file_id(day)
        try:
            if fid:
                await bot.send_photo(user_id, photo=fid, caption=narrative)
            else:
                await bot.send_message(user_id, narrative)
        except TelegramRetryAfter as e:
            logger.warning("Rate limited sending miniquest to %s, sleep %ss", user_id, e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                if fid:
                    await bot.send_photo(user_id, photo=fid, caption=narrative)
                else:
                    await bot.send_message(user_id, narrative)
            except TelegramForbiddenError:
                await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1", user_id)
                continue
            except Exception:
                logger.exception("Miniquest retry failed for user %s", user_id)
                continue
        except TelegramForbiddenError:
            await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1", user_id)
            continue
        except Exception:
            logger.exception("Miniquest send failed for user %s", user_id)
            continue

        await asyncio.sleep(BROADCAST_DELAY)

        statement = await get_statement_for_miniquest(weapon, day, redis_conn)
        stmt_text = (
            f"📜 <b>Утверждение:</b>\n<i>«{statement.text}»</i>\n\n"
            "Это <b>ПРАВДА</b> или <b>ЛОЖЬ</b>?"
        )

        await redis_conn.setex(
            f"miniquest:pending:{user_id}",
            86400,
            f"{day}|{1 if statement.is_truth else 0}",
        )

        try:
            await bot.send_message(
                user_id,
                stmt_text,
                reply_markup=get_miniquest_answer_keyboard(day),
            )
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(
                    user_id, stmt_text,
                    reply_markup=get_miniquest_answer_keyboard(day),
                )
            except Exception:
                logger.exception("Miniquest statement retry failed for user %s", user_id)
        except TelegramForbiddenError:
            await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1", user_id)
            continue
        except Exception:
            logger.exception("Miniquest statement send failed for user %s", user_id)

        await asyncio.sleep(BROADCAST_DELAY)
        sent += 1

    if sent:
        logger.info("Daily miniquests sent: %d", sent)
    return sent
