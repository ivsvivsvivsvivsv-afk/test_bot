"""
Web flow HTTP transport for full quest scenario.

Implements:
- session start/state
- action handling with optimistic locking
- lead submit
- payment create
- SSE stream for session updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from typing import Any

import asyncpg
from aiohttp import web
from redis.asyncio import Redis

from keyboards.inline import HERO_CLASSES, WEAPONS
from services.payment_service import create_payment, try_hold_slot
from services.quest_service import (
    complete_quest,
    get_or_create_user,
    log_event,
    save_class,
    save_round_result,
    save_round_start,
    save_weapon,
    update_quest_state,
)
from services.scenario_registry import resolve_scenario_context
from utils.content_registry import get as content_get
from utils.content_manager import ContentManager
from utils.statements import Statement, format_round_result, format_statement, get_statement_for_round

logger = logging.getLogger(__name__)

SESSION_TTL_SEC = 60 * 60 * 24 * 7
IDEMP_TTL_SEC = 60 * 60
WEB_USER_ID_BASE = 9_100_000_000
WEB_USER_ID_MAX = 9_999_999_999

CLASS_ALIASES = {
    "бизнесмен": "businessman",
    "творец": "creator",
    "аналитик": "analyst",
    "менеджер": "manager",
}
WEAPON_ALIASES = {
    "маркетинг": "marketing",
    "analytics": "analytics",
    "аналитика": "analytics",
    "копирайтинг": "copywriting",
    "дизайн": "design",
    "менеджмент": "management",
    "видео": "video",
}


def _pool(request: web.Request) -> asyncpg.Pool:
    from bot import POOL_KEY

    pool = request.app.get(POOL_KEY)
    if not pool:
        raise web.HTTPServiceUnavailable(text="DB pool is not ready")
    return pool


def _redis(request: web.Request) -> Redis:
    from bot import REDIS_CONN_KEY

    redis_conn = request.app.get(REDIS_CONN_KEY)
    if not redis_conn:
        raise web.HTTPServiceUnavailable(text="Redis is not ready")
    return redis_conn


def _json(data: dict[str, Any], status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


def _session_key(token: str) -> str:
    return f"web:session:{token}"


def _idempotency_key(token: str, key: str) -> str:
    return f"web:idemp:{token}:{key}"


def _extract_session_token(request: web.Request) -> str | None:
    token = request.headers.get("X-Session-Token", "").strip()
    if token:
        return token
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.query.get("session_token", "").strip() or None


async def _load_session(redis_conn: Redis, token: str) -> dict[str, Any] | None:
    raw = await redis_conn.get(_session_key(token))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def _save_session(redis_conn: Redis, token: str, session: dict[str, Any]) -> None:
    await redis_conn.setex(_session_key(token), SESSION_TTL_SEC, json.dumps(session, ensure_ascii=False))


async def _next_web_user_id(redis_conn: Redis) -> int:
    seq = int(await redis_conn.incr("web:user:id:seq"))
    candidate = WEB_USER_ID_BASE + seq
    if candidate > WEB_USER_ID_MAX:
        logger.warning("web:user:id sequence reached max, wrapping")
        await redis_conn.set("web:user:id:seq", 0)
        candidate = WEB_USER_ID_BASE + 1
    return candidate


def _is_winner(score: int) -> bool:
    """Победа при 2/3 и 3/3, поражение при 0/3 и 1/3."""
    return score >= 2


def _quest_result_text(
    score: int, hero_class: str, weapon: str, first_name: str, bundle_id: str = "default"
) -> str:
    """Осмысленный текст результата: победа или поражение."""
    if _is_winner(score):
        return content_get(bundle_id, "result_win", first_name=first_name)
    return content_get(bundle_id, "result_lose", first_name=first_name)


def _normalize_choice(
    raw_value: Any,
    *,
    allowed: set[str],
    aliases: dict[str, str],
    legacy_prefix: str,
) -> str | None:
    if raw_value is None:
        return None
    raw = str(raw_value).strip().lower()
    if not raw:
        return None

    # Telegram-style callback payloads and prefixed legacy values.
    if ":" in raw:
        raw = raw.split(":")[-1].strip()
    if raw.startswith(legacy_prefix):
        raw = raw[len(legacy_prefix) :].strip()

    if raw in allowed:
        return raw
    if raw in aliases and aliases[raw] in allowed:
        return aliases[raw]

    # Tolerant parse for labels such as "💼 Бизнесмен".
    for alias, normalized in aliases.items():
        if alias in raw and normalized in allowed:
            return normalized
    return None


def _normalize_answer(raw_value: Any) -> bool | None:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return None
    raw = str(raw_value).strip().lower()
    if ":" in raw:
        raw = raw.split(":")[-1].strip()
    if raw in {"true", "1", "yes", "да", "правда"}:
        return True
    if raw in {"false", "0", "no", "нет", "ложь"}:
        return False
    return None


def _build_ui_payload(session: dict[str, Any]) -> dict[str, Any]:
    step = session["step"]
    bundle_id = session.get("bundle_id", "default")
    if step == "welcome":
        return {
            "text": content_get(bundle_id, "welcome"),
            "actions": [{"id": "begin", "label": "Начать квест"}],
            "media_key": "img_start",
        }
    if step == "prepare":
        return {
            "text": content_get(bundle_id, "quest_intro"),
            "actions": [{"id": "ready", "label": "Готов"}],
            "media_key": "img_prepare",
        }
    if step == "class_selection":
        return {
            "text": content_get(bundle_id, "select_class"),
            "actions": [{"id": "select_class", "label": v["name"], "value": k} for k, v in HERO_CLASSES.items()],
            "media_key": "img_free_boss",
        }
    if step == "weapon_selection":
        hero_class = session.get("hero_class", "businessman")
        class_info = HERO_CLASSES.get(hero_class, HERO_CLASSES["businessman"])
        return {
            "text": content_get(
                bundle_id,
                "class_selected",
                class_name=class_info["name"],
                class_desc=class_info["desc"],
            ),
            "actions": [{"id": "select_weapon", "label": v["name"], "value": k} for k, v in WEAPONS.items()],
            "media_key": "img_proff",
        }
    if step.startswith("round_") and step.count("_") == 1:
        statement = Statement(
            text=session["current_statement_text"],
            is_truth=bool(session["current_statement_is_truth"]),
            wisdom_prompt=session["current_statement_wisdom"],
            level=int(step.split("_")[1]),
        )
        return {
            "text": format_statement(statement, int(step.split("_")[1]), int(session.get("score", 0))),
            "actions": [
                {"id": "answer_round", "label": "Правда", "value": True},
                {"id": "answer_round", "label": "Ложь", "value": False},
            ],
        }
    if step.startswith("round_result_"):
        round_num = int(step.split("_")[-1])
        last_correct = bool(session.get("last_correct", False))
        score = int(session.get("score", 0))
        statement = Statement(
            text=session.get("current_statement_text", ""),
            is_truth=bool(session.get("current_statement_is_truth", False)),
            wisdom_prompt=session.get("current_statement_wisdom", ""),
            level=round_num,
        )
        actions = [{"id": "next_round", "label": "Следующий раунд"}]
        if round_num >= 3:
            actions = [{"id": "show_result", "label": "Узнать результат"}]
        return {
            "text": format_round_result(last_correct, round_num, score, statement, bundle_id),
            "actions": actions,
            "media_key": "img_kill" if last_correct else "img_gidratt",
        }
    if step == "quest_result":
        score = int(session.get("score", 0))
        is_win = _is_winner(score)
        actions = (
            [{"id": "to_prize", "label": "Получить подарок"}]
            if is_win
            else [{"id": "to_moral", "label": "Узнать мораль"}]
        )
        return {
            "text": _quest_result_text(
                score,
                session.get("hero_class", "businessman"),
                session.get("weapon", "marketing"),
                "Воин",
                session.get("bundle_id", "default"),
            ),
            "actions": actions,
            "media_key": "img_win" if is_win else "img_lose",
        }
    if step == "prize":
        return {
            "text": content_get(bundle_id, "prize_intro"),
            "actions": [{"id": "to_lead_form", "label": "Оставить контакты"}],
            "media_key": "img_win",
        }
    if step == "moral":
        return {
            "text": content_get(bundle_id, "moral"),
            "actions": [{"id": "open_lead_form", "label": "Оставить контакты"}],
            "media_key": "img_stark",
        }
    if step == "lead_form":
        return {
            "text": content_get(bundle_id, "contact_intro"),
            "actions": [{"id": "submit_lead", "label": "Отправить лид"}],
            "lead_schema": {
                "required": ["phone"],
                "optional": ["email", "first_name"],
            },
        }
    if step == "offer":
        return {
            "text": "Готово! Оставьте заявку на воркшоп или перейдите к оплате персонального разбора.",
            "actions": [{"id": "create_payment", "label": "Оплатить 5000"}],
        }
    if step == "payment_pending":
        return {
            "text": "Платеж создан. Перейдите по ссылке.",
            "actions": [{"id": "payment_redirect", "label": "Перейти к оплате", "url": session.get("payment_url")}],
        }
    return {"text": "Сессия завершена", "actions": []}


def _snapshot(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "step": session["step"],
        "step_id": session["step"],
        "state_version": int(session["state_version"]),
        "score": int(session.get("score", 0)),
        "hero_class": session.get("hero_class"),
        "weapon": session.get("weapon"),
        "ui_payload": _build_ui_payload(session),
    }


async def post_web_session_start(request: web.Request) -> web.Response:
    redis_conn = _redis(request)
    pool = _pool(request)
    payload = await request.json() if request.can_read_body else {}

    scenario_ctx = resolve_scenario_context(
        client_type=str(payload.get("client_type", "web")),
        scenario_id=str(payload.get("scenario_id", "web_l1")),
        ab_variant=str(payload.get("ab_variant", "a")),
    )
    user_id = await _next_web_user_id(redis_conn)
    utm_source = str(payload.get("utm_source", "web_organic")).strip().lower() or "web_organic"

    await get_or_create_user(
        pool,
        user_id=user_id,
        username=None,
        first_name=payload.get("first_name"),
        source=utm_source,
        client_type=scenario_ctx.client_type,
        scenario_id=scenario_ctx.scenario_id,
        ab_variant=scenario_ctx.ab_variant,
    )
    await update_quest_state(pool, user_id, "start")
    await log_event(
        pool,
        user_id,
        "bot_start",
        {
            "source": utm_source,
            "client_type": scenario_ctx.client_type,
            "scenario_id": scenario_ctx.scenario_id,
            "ab_variant": scenario_ctx.ab_variant,
            "referrer": payload.get("referrer"),
        },
    )

    token = secrets.token_urlsafe(32)
    session = {
        "user_id": user_id,
        "client_type": scenario_ctx.client_type,
        "scenario_id": scenario_ctx.scenario_id,
        "ab_variant": scenario_ctx.ab_variant,
        "utm_source": utm_source,
        "step": "welcome",
        "state_version": 1,
        "score": 0,
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    await _save_session(redis_conn, token, session)
    return _json({"ok": True, "session_token": token, "state_snapshot": _snapshot(session)})


async def get_web_session_state(request: web.Request) -> web.Response:
    redis_conn = _redis(request)
    token = _extract_session_token(request)
    if not token:
        return _json({"ok": False, "error": "missing_session_token"}, status=401)
    session = await _load_session(redis_conn, token)
    if not session:
        return _json({"ok": False, "error": "session_not_found"}, status=404)
    return _json({"ok": True, "session_token": token, "state_snapshot": _snapshot(session)})


async def post_web_action(request: web.Request) -> web.Response:
    redis_conn = _redis(request)
    pool = _pool(request)
    token = _extract_session_token(request)
    if not token:
        return _json({"ok": False, "error": "missing_session_token"}, status=401)
    session = await _load_session(redis_conn, token)
    if not session:
        return _json({"ok": False, "error": "session_not_found"}, status=404)

    payload = await request.json() if request.can_read_body else {}
    action_type = str(payload.get("action_type", "")).strip()
    if not action_type:
        return _json({"ok": False, "error": "action_type_required"}, status=400)

    idempotency_key = str(payload.get("idempotency_key", "")).strip()
    if idempotency_key:
        id_key = _idempotency_key(token, idempotency_key)
        cached = await redis_conn.get(id_key)
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return web.Response(text=cached, content_type="application/json")

    client_version = payload.get("state_version")
    if client_version is None:
        return _json({"ok": False, "error": "state_version_required"}, status=400)
    if int(client_version) != int(session["state_version"]):
        return _json(
            {
                "ok": False,
                "error": "state_version_conflict",
                "code": "state_version_conflict",
                "state_snapshot": _snapshot(session),
            },
            status=409,
        )

    user_id = int(session["user_id"])
    step = session["step"]
    action_payload = payload.get("payload") or {}

    if action_type == "begin" and step == "welcome":
        session["step"] = "prepare"
        await update_quest_state(pool, user_id, "quest_intro")
        await log_event(pool, user_id, "quest_start", {})
    elif action_type == "ready" and step == "prepare":
        session["step"] = "class_selection"
        await log_event(pool, user_id, "prepare_done", {})
    elif action_type == "select_class" and step == "class_selection":
        class_id = _normalize_choice(
            action_payload.get("class_id") or action_payload.get("classId") or action_payload.get("value"),
            allowed=set(HERO_CLASSES.keys()),
            aliases=CLASS_ALIASES,
            legacy_prefix="class_",
        )
        if not class_id:
            return _json({"ok": False, "error": "invalid_class"}, status=400)
        session["hero_class"] = class_id
        session["step"] = "weapon_selection"
        await save_class(pool, user_id, class_id)
        await log_event(pool, user_id, "class_selected", {"class": class_id})
    elif action_type == "select_weapon" and step == "weapon_selection":
        weapon_id = _normalize_choice(
            action_payload.get("weapon_id") or action_payload.get("weaponId") or action_payload.get("value"),
            allowed=set(WEAPONS.keys()),
            aliases=WEAPON_ALIASES,
            legacy_prefix="weapon_",
        )
        if not weapon_id:
            return _json({"ok": False, "error": "invalid_weapon"}, status=400)
        session["weapon"] = weapon_id
        session["current_round"] = 1
        bundle_id = session.get("bundle_id", "default")
        statement = await get_statement_for_round(weapon_id, 1, redis_conn, bundle_id)
        session["current_statement_text"] = statement.text
        session["current_statement_is_truth"] = statement.is_truth
        session["current_statement_wisdom"] = statement.wisdom_prompt
        session["step"] = "round_1"
        await save_weapon(pool, user_id, weapon_id)
        await save_round_start(pool, user_id, 1, statement.text, statement.is_truth)
        await log_event(pool, user_id, "weapon_selected", {"weapon": weapon_id})
    elif action_type == "answer_round" and step.startswith("round_") and step.count("_") == 1:
        round_num = int(step.split("_")[1])
        if "answer" in action_payload:
            raw_answer = action_payload.get("answer")
        elif "value" in action_payload:
            raw_answer = action_payload.get("value")
        elif "answer" in payload:
            raw_answer = payload.get("answer")
        else:
            raw_answer = payload.get("value")
        answer_bool = _normalize_answer(raw_answer)
        if answer_bool is None:
            return _json({"ok": False, "error": "invalid_answer"}, status=400)
        is_truth = bool(session.get("current_statement_is_truth", False))
        is_correct = answer_bool == is_truth
        if is_correct:
            session["score"] = int(session.get("score", 0)) + 1
        session["last_correct"] = is_correct
        session["step"] = f"round_result_{round_num}"
        await save_round_result(pool, user_id, round_num, int(session["score"]))
        await log_event(
            pool,
            user_id,
            "round_completed",
            {"round": round_num, "correct": is_correct, "score": int(session["score"])},
        )
    elif action_type == "next_round" and step in {"round_result_1", "round_result_2"}:
        current = int(step.split("_")[-1]) + 1
        session["current_round"] = current
        bundle_id = session.get("bundle_id", "default")
        statement = await get_statement_for_round(
            session["weapon"], current, redis_conn, bundle_id
        )
        session["current_statement_text"] = statement.text
        session["current_statement_is_truth"] = statement.is_truth
        session["current_statement_wisdom"] = statement.wisdom_prompt
        session["step"] = f"round_{current}"
        await save_round_start(pool, user_id, current, statement.text, statement.is_truth)
    elif action_type == "show_result" and step == "round_result_3":
        session["step"] = "quest_result"
        await complete_quest(pool, user_id, int(session.get("score", 0)))
        await log_event(pool, user_id, "quest_completed", {"score": int(session.get("score", 0))})
    elif action_type == "to_prize" and step == "quest_result":
        if not _is_winner(int(session.get("score", 0))):
            return _json({"ok": False, "error": "invalid_action_for_step", "step": step}, status=400)
        session["step"] = "prize"
        await update_quest_state(pool, user_id, "prize")
    elif action_type == "to_moral" and step == "quest_result":
        session["step"] = "moral"
        await update_quest_state(pool, user_id, "moral")
    elif action_type in ("to_lead_form", "get_prize") and step == "prize":
        session["step"] = "lead_form"
    elif action_type == "open_lead_form" and step == "moral":
        session["step"] = "lead_form"
    elif action_type == "submit_lead" and step == "lead_form":
        phone = str(action_payload.get("phone", "")).strip()
        email = str(action_payload.get("email", "")).strip() or None
        if not phone:
            return _json({"ok": False, "error": "phone_required"}, status=400)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET phone = $2, email = COALESCE($3, email), workshop_registered = TRUE
                WHERE user_id = $1
                """,
                user_id,
                phone,
                email,
            )
        await log_event(pool, user_id, "contact_phone", {"phone": phone})
        await log_event(pool, user_id, "workshop_registered", {"source": "web"})
        session["step"] = "offer"
    elif action_type == "create_payment" and step == "offer":
        held = await try_hold_slot(pool, redis_conn, user_id)
        if not held:
            return _json({"ok": False, "error": "no_slots", "code": "no_slots"}, status=409)
        result = await create_payment(pool, redis_conn, user_id)
        if "error" in result:
            return _json({"ok": False, "error": result["error"], "code": result["error"]}, status=409)
        session["step"] = "payment_pending"
        session["payment_url"] = result["url"]
        await log_event(pool, user_id, "payment_create", {"payment_id": result["payment_id"]})
    else:
        return _json({"ok": False, "error": "invalid_action_for_step", "step": step}, status=400)

    session["state_version"] = int(session["state_version"]) + 1
    session["updated_at"] = int(time.time())
    await _save_session(redis_conn, token, session)
    response_body = {
        "ok": True,
        "session_token": token,
        "state_snapshot": _snapshot(session),
    }
    if idempotency_key:
        await redis_conn.setex(
            _idempotency_key(token, idempotency_key),
            IDEMP_TTL_SEC,
            json.dumps(response_body, ensure_ascii=False),
        )
    return _json(response_body)


async def post_web_contact_submit(request: web.Request) -> web.Response:
    """
    Convenience endpoint for clients that submit lead separately from /action.
    """
    redis_conn = _redis(request)
    pool = _pool(request)
    token = _extract_session_token(request)
    if not token:
        return _json({"ok": False, "error": "missing_session_token"}, status=401)
    session = await _load_session(redis_conn, token)
    if not session:
        return _json({"ok": False, "error": "session_not_found"}, status=404)
    if session["step"] != "lead_form":
        return _json({"ok": False, "error": "invalid_step_for_contact", "step": session["step"]}, status=400)

    payload = await request.json() if request.can_read_body else {}
    client_version = payload.get("state_version")
    if client_version is None:
        return _json({"ok": False, "error": "state_version_required"}, status=400)
    if int(client_version) != int(session["state_version"]):
        return _json(
            {
                "ok": False,
                "error": "state_version_conflict",
                "code": "state_version_conflict",
                "state_snapshot": _snapshot(session),
            },
            status=409,
        )

    phone = str(payload.get("phone", "")).strip()
    email = str(payload.get("email", "")).strip() or None
    if not phone:
        return _json({"ok": False, "error": "phone_required"}, status=400)

    user_id = int(session["user_id"])
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET phone = $2, email = COALESCE($3, email), workshop_registered = TRUE
            WHERE user_id = $1
            """,
            user_id,
            phone,
            email,
        )
    await log_event(pool, user_id, "contact_phone", {"phone": phone})
    await log_event(pool, user_id, "workshop_registered", {"source": "web"})

    session["step"] = "offer"
    session["state_version"] = int(session["state_version"]) + 1
    session["updated_at"] = int(time.time())
    await _save_session(redis_conn, token, session)
    return _json({"ok": True, "session_token": token, "state_snapshot": _snapshot(session)})


async def post_web_payment_create(request: web.Request) -> web.Response:
    redis_conn = _redis(request)
    pool = _pool(request)
    token = _extract_session_token(request)
    if not token:
        return _json({"ok": False, "error": "missing_session_token"}, status=401)
    session = await _load_session(redis_conn, token)
    if not session:
        return _json({"ok": False, "error": "session_not_found"}, status=404)
    if session["step"] != "offer":
        return _json({"ok": False, "error": "invalid_step_for_payment", "step": session["step"]}, status=400)

    payload = await request.json() if request.can_read_body else {}
    client_version = payload.get("state_version")
    if client_version is None:
        return _json({"ok": False, "error": "state_version_required"}, status=400)
    if int(client_version) != int(session["state_version"]):
        return _json(
            {
                "ok": False,
                "error": "state_version_conflict",
                "code": "state_version_conflict",
                "state_snapshot": _snapshot(session),
            },
            status=409,
        )

    user_id = int(session["user_id"])
    held = await try_hold_slot(pool, redis_conn, user_id)
    if not held:
        return _json({"ok": False, "error": "no_slots", "code": "no_slots"}, status=409)
    result = await create_payment(pool, redis_conn, user_id)
    if "error" in result:
        return _json({"ok": False, "error": result["error"], "code": result["error"]}, status=409)

    session["step"] = "payment_pending"
    session["payment_url"] = result["url"]
    session["state_version"] = int(session["state_version"]) + 1
    session["updated_at"] = int(time.time())
    await _save_session(redis_conn, token, session)
    await log_event(pool, user_id, "payment_create", {"payment_id": result["payment_id"]})
    return _json({"ok": True, "session_token": token, "state_snapshot": _snapshot(session)})


async def get_web_stream(request: web.Request) -> web.StreamResponse:
    redis_conn = _redis(request)
    token = _extract_session_token(request)
    if not token:
        raise web.HTTPUnauthorized(text="missing_session_token")

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    last_version = -1
    heartbeat_at = 0.0
    try:
        while True:
            now = time.monotonic()
            session = await _load_session(redis_conn, token)
            if not session:
                await resp.write(
                    b"event: force_refresh\ndata: {\"type\":\"force_refresh\",\"reason\":\"session_expired\"}\n\n"
                )
                break
            current_version = int(session.get("state_version", 0))
            if current_version != last_version:
                data = json.dumps(
                    {"type": "session_updated", "state_snapshot": _snapshot(session)},
                    ensure_ascii=False,
                ).encode("utf-8")
                await resp.write(b"event: session_updated\n")
                await resp.write(b"data: " + data + b"\n\n")
                last_version = current_version
            if now - heartbeat_at > 20:
                await resp.write(b": heartbeat\n\n")
                heartbeat_at = now
            await asyncio.sleep(2)
    except (ConnectionResetError, asyncio.CancelledError):
        logger.info("SSE stream closed for token=%s", token[:8])
    finally:
        try:
            await resp.write_eof()
        except Exception:
            pass
    return resp


async def _web_ping(_request: web.Request) -> web.Response:
    """Debug: verify /api/web/ routes are reachable."""
    return web.json_response({"pong": True, "route": "api/web"})


def register_web_flow_routes(app: web.Application) -> None:
    app.router.add_get("/api/web/ping", _web_ping)
    app.router.add_post("/api/web/session/start", post_web_session_start)
    app.router.add_get("/api/web/session/state", get_web_session_state)
    app.router.add_post("/api/web/action", post_web_action)
    app.router.add_post("/api/web/contact/submit", post_web_contact_submit)
    app.router.add_post("/api/web/payment/create", post_web_payment_create)
    app.router.add_get("/api/web/stream", get_web_stream)

