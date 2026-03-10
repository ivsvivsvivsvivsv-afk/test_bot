"""
HTTP API for unified admin panel (neurounit.fun/admin).

Security:
- X-Admin-Secret / X-Site-Secret with constant-time compare.
- Redis IP rate-limit.
"""

from __future__ import annotations

import hmac
import json
import logging
import re
from datetime import datetime
from typing import Any

import asyncpg
from aiohttp import web
from aiogram import Bot
from redis.asyncio import Redis

from config import ADMIN_API_SECRET, SITE_WEBHOOK_SECRET
from services.broadcast_service import broadcast_segment, count_segment_users
from services.quest_service import log_event

logger = logging.getLogger(__name__)


def _json(data: dict[str, Any], status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


def _client_ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "").strip()
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote or "unknown"


async def _rate_limit(
    redis_conn: Redis | None,
    *,
    key: str,
    limit_per_minute: int,
) -> bool:
    if redis_conn is None:
        # Fail-open for availability if Redis is unavailable.
        return True
    try:
        current = await redis_conn.incr(key)
        if current == 1:
            await redis_conn.expire(key, 60)
        return int(current) <= limit_per_minute
    except Exception:
        logger.exception("Rate limit failed for key=%s", key)
        return True


def _secure_compare(provided: str, expected: str) -> bool:
    if not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


async def _require_admin_auth(request: web.Request) -> web.Response | None:
    if not ADMIN_API_SECRET:
        return _json({"ok": False, "error": "admin_api_not_configured"}, status=503)

    from bot import REDIS_CONN_KEY
    redis_conn: Redis | None = request.app.get(REDIS_CONN_KEY)
    ip = _client_ip(request)
    allowed = await _rate_limit(
        redis_conn,
        key=f"rl:admin_api:{ip}",
        limit_per_minute=60,
    )
    if not allowed:
        return _json({"ok": False, "error": "rate_limited"}, status=429)

    provided = request.headers.get("X-Admin-Secret", "")
    if not _secure_compare(provided, ADMIN_API_SECRET):
        logger.warning("Admin API unauthorized from ip=%s path=%s", ip, request.path)
        return _json({"ok": False, "error": "unauthorized"}, status=401)
    return None


async def _require_site_auth(request: web.Request) -> web.Response | None:
    if not SITE_WEBHOOK_SECRET:
        return _json({"ok": False, "error": "site_webhook_not_configured"}, status=503)

    from bot import REDIS_CONN_KEY
    redis_conn: Redis | None = request.app.get(REDIS_CONN_KEY)
    ip = _client_ip(request)
    allowed = await _rate_limit(
        redis_conn,
        key=f"rl:site_webhook:{ip}",
        limit_per_minute=30,
    )
    if not allowed:
        return _json({"ok": False, "error": "rate_limited"}, status=429)

    provided = request.headers.get("X-Site-Secret", "")
    if not _secure_compare(provided, SITE_WEBHOOK_SECRET):
        logger.warning("Site webhook unauthorized from ip=%s", ip)
        return _json({"ok": False, "error": "unauthorized"}, status=401)
    return None


def _pool(request: web.Request) -> asyncpg.Pool:
    from bot import POOL_KEY
    pool = request.app.get(POOL_KEY)
    if not pool:
        raise web.HTTPServiceUnavailable(text="DB pool is not ready")
    return pool


def _bot(request: web.Request) -> Bot:
    from bot import BOT_KEY
    bot = request.app.get(BOT_KEY)
    if not bot:
        raise web.HTTPServiceUnavailable(text="Bot is not ready")
    return bot


async def get_admin_stats(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    pool = _pool(request)
    async with pool.acquire() as conn:
        users_total = await conn.fetchval("SELECT COUNT(*)::int FROM users") or 0
        users_today = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE created_at >= date_trunc('day', NOW())"
        ) or 0
        users_blocked = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE is_blocked = TRUE"
        ) or 0
        leads_quest = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE workshop_registered = TRUE"
        ) or 0
        leads_arena = await conn.fetchval(
            "SELECT COUNT(*)::int FROM users WHERE arena_registered = TRUE"
        ) or 0
        payments = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'succeeded')::int AS succeeded,
                COALESCE(SUM(amount) FILTER (WHERE status = 'succeeded'), 0)::float AS revenue
            FROM payments
            """
        )

    return _json(
        {
            "ok": True,
            "users_total": users_total,
            "users_today": users_today,
            "users_blocked": users_blocked,
            "leads_quest": leads_quest,
            "leads_arena": leads_arena,
            "payments_succeeded": int(payments["succeeded"] or 0),
            "revenue": float(payments["revenue"] or 0),
        }
    )


async def get_admin_funnel(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    days = request.query.get("days", "7")
    try:
        days_int = max(1, min(int(days), 90))
    except ValueError:
        days_int = 7

    pool = _pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'bot_start')::int AS visitors,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'quest_start')::int AS quest_started,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'class_selected')::int AS class_selected,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'weapon_selected')::int AS weapon_selected,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'quest_completed')::int AS quest_completed,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'workshop_registered')::int AS workshop_registered,
                COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'payment_succeeded')::int AS paid
            FROM events
            WHERE created_at >= NOW() - make_interval(days => $1)
            """,
            days_int,
        )

    visitors = int(row["visitors"] or 0)
    steps = [
        ("Посетители", visitors),
        ("Начали квест", int(row["quest_started"] or 0)),
        ("Выбрали класс", int(row["class_selected"] or 0)),
        ("Выбрали оружие", int(row["weapon_selected"] or 0)),
        ("Завершили квест", int(row["quest_completed"] or 0)),
        ("Записались на воркшоп", int(row["workshop_registered"] or 0)),
        ("Оплатили", int(row["paid"] or 0)),
    ]
    payload_steps = []
    prev = visitors if visitors > 0 else 1
    for idx, (name, count) in enumerate(steps):
        if idx == 0:
            conv = 100.0
        else:
            conv = round((count / prev) * 100, 2) if prev > 0 else 0.0
        payload_steps.append({"name": name, "count": count, "conversion": conv})
        prev = count if count > 0 else prev

    return _json({"ok": True, "days": days_int, "steps": payload_steps})


async def get_admin_button_stats(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    days = request.query.get("days", "7")
    try:
        days_int = max(1, min(int(days), 90))
    except ValueError:
        days_int = 7

    pool = _pool(request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(event_data->>'callback', 'unknown') AS callback,
                COUNT(*)::int AS clicks,
                COUNT(DISTINCT user_id)::int AS unique_users
            FROM events
            WHERE event_type = 'button_click'
              AND created_at >= NOW() - make_interval(days => $1)
            GROUP BY callback
            ORDER BY clicks DESC
            LIMIT 100
            """,
            days_int,
        )

    items = [
        {
            "callback": r["callback"],
            "clicks": int(r["clicks"]),
            "unique_users": int(r["unique_users"]),
        }
        for r in rows
    ]
    return _json({"ok": True, "days": days_int, "items": items})


async def get_admin_leads(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    limit = request.query.get("limit", "50")
    offset = request.query.get("offset", "0")
    status = request.query.get("status", "").strip()
    search = request.query.get("search", "").strip()
    try:
        limit_int = max(1, min(int(limit), 500))
    except ValueError:
        limit_int = 50
    try:
        offset_int = max(0, int(offset))
    except ValueError:
        offset_int = 0

    clauses = ["(u.phone IS NOT NULL OR u.arena_registered = TRUE)"]
    params: list[Any] = []
    idx = 1

    if status:
        clauses.append(f"COALESCE(ls.status, 'new') = ${idx}")
        params.append(status)
        idx += 1
    if search:
        clauses.append(
            f"(u.first_name ILIKE ${idx} OR u.username ILIKE ${idx} OR COALESCE(u.phone, '') ILIKE ${idx})"
        )
        params.append(f"%{search}%")
        idx += 1

    where_sql = " AND ".join(clauses)
    limit_param = idx
    offset_param = idx + 1
    params.extend([limit_int, offset_int])

    pool = _pool(request)
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"""
            SELECT COUNT(*)::int
            FROM users u
            LEFT JOIN lead_statuses ls ON ls.user_id = u.user_id
            WHERE {where_sql}
            """,
            *params[:-2],
        ) or 0

        rows = await conn.fetch(
            f"""
            SELECT
                u.user_id, u.username, u.first_name, u.phone, u.email,
                u.player_class, u.weapon, u.workshop_registered, u.arena_registered,
                u.created_at,
                COALESCE(ls.status, 'new') AS status
            FROM users u
            LEFT JOIN lead_statuses ls ON ls.user_id = u.user_id
            WHERE {where_sql}
            ORDER BY u.created_at DESC
            LIMIT ${limit_param} OFFSET ${offset_param}
            """,
            *params,
        )

    leads = []
    for r in rows:
        source = "quest" if r["workshop_registered"] else "arena" if r["arena_registered"] else "unknown"
        leads.append(
            {
                "user_id": int(r["user_id"]),
                "username": r["username"],
                "first_name": r["first_name"],
                "phone": r["phone"],
                "email": r["email"],
                "source": source,
                "status": r["status"],
                "player_class": r["player_class"],
                "weapon": r["weapon"],
                "workshop_registered": bool(r["workshop_registered"]),
                "arena_registered": bool(r["arena_registered"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
        )
    return _json({"ok": True, "total": int(total), "leads": leads})


async def post_admin_lead_note(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    user_id = int(request.match_info["user_id"])
    payload = await request.json()
    note = str(payload.get("note", "")).strip()
    admin_id = int(payload.get("admin_id", 0) or 0)
    if not note:
        return _json({"ok": False, "error": "note_required"}, status=400)
    if admin_id <= 0:
        return _json({"ok": False, "error": "admin_id_required"}, status=400)

    pool = _pool(request)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO lead_notes (user_id, admin_id, note)
            VALUES ($1, $2, $3)
            """,
            user_id,
            admin_id,
            note,
        )
    return _json({"ok": True})


async def put_admin_lead_status(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    user_id = int(request.match_info["user_id"])
    payload = await request.json()
    status = str(payload.get("status", "")).strip()
    updated_by = int(payload.get("updated_by", 0) or 0)
    allowed = {"new", "contacted", "qualified", "converted", "lost"}
    if status not in allowed:
        return _json({"ok": False, "error": "invalid_status"}, status=400)
    if updated_by <= 0:
        return _json({"ok": False, "error": "updated_by_required"}, status=400)

    pool = _pool(request)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO lead_statuses (user_id, status, updated_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                updated_at = NOW(),
                updated_by = EXCLUDED.updated_by
            """,
            user_id,
            status,
            updated_by,
        )
    return _json({"ok": True})


async def get_admin_segments(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    pool = _pool(request)
    static_segments = [
        ("all", "Все активные"),
        ("visitors", "Зашли в бота"),
        ("quest_started", "Начали квест"),
        ("quest_in_progress", "В процессе квеста"),
        ("quest_completed", "Завершили квест"),
        ("workshop_registered", "Записались на воркшоп"),
        ("not_workshop", "Прошли квест, не записались"),
        ("arena_only", "Только арена"),
        ("has_phone", "Оставили телефон"),
        ("paid", "Оплатили"),
        ("followup_day1", "День 1 дожима"),
        ("followup_day2_5", "Дни 2-5 дожима"),
    ]
    items: list[dict[str, Any]] = []
    for sid, label in static_segments:
        cnt = await count_segment_users(pool, sid)
        items.append({"id": sid, "name": label, "count": cnt})

    async with pool.acquire() as conn:
        for row in await conn.fetch("SELECT DISTINCT player_class FROM users WHERE player_class IS NOT NULL"):
            sid = f"by_class:{row['player_class']}"
            cnt = await count_segment_users(pool, sid)
            items.append({"id": sid, "name": f"Класс: {row['player_class']}", "count": cnt})
        for row in await conn.fetch("SELECT DISTINCT weapon FROM users WHERE weapon IS NOT NULL"):
            sid = f"by_weapon:{row['weapon']}"
            cnt = await count_segment_users(pool, sid)
            items.append({"id": sid, "name": f"Оружие: {row['weapon']}", "count": cnt})
        for row in await conn.fetch("SELECT DISTINCT utm_source FROM users WHERE utm_source IS NOT NULL"):
            sid = f"by_utm:{row['utm_source']}"
            cnt = await count_segment_users(pool, sid)
            items.append({"id": sid, "name": f"UTM: {row['utm_source']}", "count": cnt})

    return _json({"ok": True, "segments": items})


async def post_admin_broadcast(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error

    payload = await request.json()
    text = str(payload.get("text", "")).strip()
    segment_id = str(payload.get("segment_id", "all")).strip() or "all"
    preview = bool(payload.get("preview", False))
    scheduled_at_raw = payload.get("scheduled_at")
    created_by = int(payload.get("created_by", 0) or 0)

    if not text:
        return _json({"ok": False, "error": "text_required"}, status=400)

    pool = _pool(request)
    total_recipients = await count_segment_users(pool, segment_id)

    if preview:
        return _json(
            {
                "ok": True,
                "status": "preview",
                "segment_id": segment_id,
                "total_recipients": total_recipients,
            }
        )

    if scheduled_at_raw:
        try:
            _ = datetime.fromisoformat(str(scheduled_at_raw).replace("Z", "+00:00"))
        except ValueError:
            return _json({"ok": False, "error": "invalid_scheduled_at"}, status=400)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO scheduled_broadcasts (text, segment_id, scheduled_at, created_by, status)
                VALUES ($1, $2, $3::timestamptz, $4, 'pending')
                RETURNING id
                """,
                text,
                segment_id,
                str(scheduled_at_raw),
                created_by or None,
            )
        return _json(
            {
                "ok": True,
                "status": "scheduled",
                "id": int(row["id"]),
                "segment_id": segment_id,
                "scheduled_at": scheduled_at_raw,
                "total_recipients": total_recipients,
            }
        )

    bot = _bot(request)
    result = await broadcast_segment(bot=bot, pool=pool, text=text, segment_id=segment_id)
    return _json(
        {
            "ok": True,
            "status": "sent",
            "segment_id": segment_id,
            "total_recipients": total_recipients,
            **result,
        }
    )


async def get_notification_rules(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error
    pool = _pool(request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, text_template, segment_id, trigger_type, trigger_config, enabled, created_at, updated_at
            FROM notification_rules
            ORDER BY id DESC
            """
        )
    items = []
    for r in rows:
        items.append(
            {
                "id": int(r["id"]),
                "name": r["name"],
                "text_template": r["text_template"],
                "segment_id": r["segment_id"],
                "trigger_type": r["trigger_type"],
                "trigger_config": r["trigger_config"],
                "enabled": bool(r["enabled"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
        )
    return _json({"ok": True, "items": items})


async def post_notification_rule(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error
    payload = await request.json()
    name = str(payload.get("name", "")).strip()
    text_template = str(payload.get("text_template", "")).strip()
    segment_id = str(payload.get("segment_id", "all")).strip() or "all"
    trigger_type = str(payload.get("trigger_type", "")).strip()
    trigger_config = payload.get("trigger_config", {})
    enabled = bool(payload.get("enabled", True))
    if not name or not text_template or not trigger_type:
        return _json({"ok": False, "error": "name_text_trigger_required"}, status=400)
    if not isinstance(trigger_config, dict):
        return _json({"ok": False, "error": "trigger_config_must_be_object"}, status=400)

    pool = _pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO notification_rules (name, text_template, segment_id, trigger_type, trigger_config, enabled)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            RETURNING id
            """,
            name,
            text_template,
            segment_id,
            trigger_type,
            json.dumps(trigger_config, ensure_ascii=False),
            enabled,
        )
    return _json({"ok": True, "id": int(row["id"])})


async def put_notification_rule(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error
    rid = int(request.match_info["rule_id"])
    payload = await request.json()

    fields = []
    params: list[Any] = [rid]
    idx = 2
    for key, col in (
        ("name", "name"),
        ("text_template", "text_template"),
        ("segment_id", "segment_id"),
        ("trigger_type", "trigger_type"),
        ("enabled", "enabled"),
    ):
        if key in payload:
            fields.append(f"{col} = ${idx}")
            params.append(payload[key])
            idx += 1
    if "trigger_config" in payload:
        if not isinstance(payload["trigger_config"], dict):
            return _json({"ok": False, "error": "trigger_config_must_be_object"}, status=400)
        fields.append(f"trigger_config = ${idx}::jsonb")
        params.append(json.dumps(payload["trigger_config"], ensure_ascii=False))
        idx += 1
    if not fields:
        return _json({"ok": False, "error": "nothing_to_update"}, status=400)
    fields.append("updated_at = NOW()")

    sql = f"UPDATE notification_rules SET {', '.join(fields)} WHERE id = $1"
    pool = _pool(request)
    async with pool.acquire() as conn:
        res = await conn.execute(sql, *params)
    return _json({"ok": True, "result": res})


async def delete_notification_rule(request: web.Request) -> web.Response:
    auth_error = await _require_admin_auth(request)
    if auth_error:
        return auth_error
    rid = int(request.match_info["rule_id"])
    pool = _pool(request)
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM notification_rules WHERE id = $1", rid)
    return _json({"ok": True, "result": res})


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return digits


async def post_site_webhook(request: web.Request) -> web.Response:
    auth_error = await _require_site_auth(request)
    if auth_error:
        return auth_error
    pool = _pool(request)
    bot = _bot(request)

    try:
        payload = await request.json()
    except Exception:
        return _json({"ok": False, "error": "invalid_json"}, status=400)

    event = str(payload.get("event", "")).strip()
    order_id = str(payload.get("order_id", "")).strip()
    user_phone = str(payload.get("user_phone", "")).strip()
    user_telegram_id = payload.get("user_telegram_id")
    metadata = payload.get("metadata", {})
    if not event:
        return _json({"ok": False, "error": "event_required"}, status=400)
    if not isinstance(metadata, dict):
        return _json({"ok": False, "error": "metadata_must_be_object"}, status=400)

    async with pool.acquire() as conn:
        if order_id:
            dup = await conn.fetchval(
                """
                SELECT 1
                FROM events
                WHERE event_type = 'site_payment_succeeded'
                  AND event_data->>'order_id' = $1
                LIMIT 1
                """,
                order_id,
            )
            if dup:
                return _json({"ok": True, "duplicate": True})

        user_id = None
        if user_telegram_id and str(user_telegram_id).isdigit():
            user_id = int(user_telegram_id)
        elif user_phone:
            norm = _normalize_phone(user_phone)
            if norm:
                user_id = await conn.fetchval(
                    """
                    SELECT user_id
                    FROM users
                    WHERE regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') = $1
                    LIMIT 1
                    """,
                    norm,
                )

    event_data = {
        "event": event,
        "order_id": order_id,
        "user_phone": user_phone,
        "user_telegram_id": user_telegram_id,
        "metadata": metadata,
    }

    if not user_id:
        logger.warning("Site webhook user not found: event=%s order_id=%s", event, order_id)
        await log_event(pool, 0, "site_payment_user_not_found", event_data)
        return _json({"ok": True, "user_found": False})

    if event == "payment_succeeded":
        text = "✅ Оплата прошла успешно! Менеджер свяжется с вами в ближайшее время."
        try:
            from utils.content_manager import ContentManager
            text = ContentManager.get_raw("site_payment_success")
        except Exception:
            pass
        try:
            await bot.send_message(chat_id=int(user_id), text=text)
        except Exception:
            logger.exception("Failed to notify user %s from site webhook", user_id)

    await log_event(pool, int(user_id), "site_payment_succeeded", event_data)
    return _json({"ok": True, "user_found": True, "user_id": int(user_id)})


def register_admin_api_routes(app: web.Application) -> None:
    app.router.add_get("/api/admin/stats", get_admin_stats)
    app.router.add_get("/api/admin/funnel", get_admin_funnel)
    app.router.add_get("/api/admin/button-stats", get_admin_button_stats)
    app.router.add_get("/api/admin/leads", get_admin_leads)
    app.router.add_post("/api/admin/leads/{user_id}/notes", post_admin_lead_note)
    app.router.add_put("/api/admin/leads/{user_id}/status", put_admin_lead_status)
    app.router.add_get("/api/admin/segments", get_admin_segments)
    app.router.add_post("/api/admin/broadcast", post_admin_broadcast)
    app.router.add_get("/api/admin/notification-rules", get_notification_rules)
    app.router.add_post("/api/admin/notification-rules", post_notification_rule)
    app.router.add_put("/api/admin/notification-rules/{rule_id}", put_notification_rule)
    app.router.add_delete("/api/admin/notification-rules/{rule_id}", delete_notification_rule)
    app.router.add_post("/api/webhook/site", post_site_webhook)
