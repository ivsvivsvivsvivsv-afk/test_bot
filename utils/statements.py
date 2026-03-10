"""
Statement loader with Redis cache.

Statements live in ``statements/{weapon}.txt`` on disk.
On first access they are parsed and cached in Redis for 1 hour so
subsequent requests skip file I/O entirely.

File format (pipe-separated):
    LEVEL|TYPE|STATEMENT|WISDOM_PROMPT
    1|false|Email-маркетинг мёртв|Проверь статистику Mailchimp
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

STATEMENTS_DIR = Path(__file__).parent.parent / "statements"
REDIS_TTL = 3600  # 1 hour

ROUND_NAMES: Dict[int, str] = {
    1: "🐉 ГОЛОВА ПЕРВАЯ: ХАОС",
    2: "🐉 ГОЛОВА ВТОРАЯ: СОМНЕНИЕ",
    3: "🐉 ГОЛОВА ТРЕТЬЯ: ИСТИНА",
}


@dataclass
class Statement:
    text: str
    is_truth: bool
    wisdom_prompt: str
    level: int


# ── Disk parser ─────────────────────────────────────────────


def _parse_file(filepath: Path) -> Dict[int, List[Statement]]:
    result: Dict[int, List[Statement]] = {1: [], 2: [], 3: []}
    if not filepath.exists():
        logger.error("Statements file not found: %s", filepath)
        return result

    with open(filepath, "r", encoding="utf-8") as fh:
        for line_num, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 4:
                logger.warning("Bad line %d in %s: %s", line_num, filepath, line[:60])
                continue
            try:
                level = int(parts[0])
                if level not in (1, 2, 3):
                    continue
                result[level].append(
                    Statement(
                        text=parts[2],
                        is_truth=parts[1].lower() == "true",
                        wisdom_prompt=parts[3],
                        level=level,
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.warning("Parse error line %d in %s: %s", line_num, filepath, exc)

    total = sum(len(v) for v in result.values())
    logger.info("Parsed %d statements from %s", total, filepath.name)
    return result


# ── Redis-cached loader ─────────────────────────────────────


def _redis_key(weapon: str) -> str:
    return f"statements:{weapon}"


async def _load_from_redis(redis_conn, weapon: str) -> Optional[Dict[int, List[Statement]]]:
    raw = await redis_conn.get(_redis_key(weapon))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        result: Dict[int, List[Statement]] = {}
        for lvl_str, items in data.items():
            result[int(lvl_str)] = [Statement(**s) for s in items]
        return result
    except Exception:
        logger.warning("Corrupt Redis cache for statements:%s, will reload", weapon)
        return None


async def _save_to_redis(
    redis_conn, weapon: str, stmts: Dict[int, List[Statement]]
) -> None:
    data = {str(k): [asdict(s) for s in v] for k, v in stmts.items()}
    try:
        await redis_conn.setex(_redis_key(weapon), REDIS_TTL, json.dumps(data, ensure_ascii=False))
    except Exception:
        logger.warning("Failed to cache statements:%s in Redis", weapon)


async def load_statements(
    weapon: str, redis_conn=None
) -> Dict[int, List[Statement]]:
    """
    Return ``{level: [Statement, ...]}`` for the given weapon.
    Uses Redis as a cache layer when available.
    """
    if redis_conn is not None:
        cached = await _load_from_redis(redis_conn, weapon)
        if cached is not None:
            return cached

    filepath = STATEMENTS_DIR / f"{weapon}.txt"
    if not filepath.exists():
        logger.warning("No file for weapon=%s, falling back to other.txt", weapon)
        filepath = STATEMENTS_DIR / "other.txt"

    stmts = _parse_file(filepath)

    if redis_conn is not None:
        await _save_to_redis(redis_conn, weapon, stmts)

    return stmts


# ── Synchronous loader (backward-compat, no Redis) ─────────


def load_statements_sync(weapon: str) -> Dict[int, List[Statement]]:
    filepath = STATEMENTS_DIR / f"{weapon}.txt"
    if not filepath.exists():
        filepath = STATEMENTS_DIR / "other.txt"
    return _parse_file(filepath)


# ── Public helpers ──────────────────────────────────────────

FALLBACK_STATEMENT = Statement(
    text="Нейросети могут заменить 100% профессий к 2030 году.",
    is_truth=False,
    wisdom_prompt="Проверь прогнозы экспертов о влиянии ИИ на рынок труда в Perplexity",
    level=1,
)


def _miniquest_level(day: int) -> int:
    """Map miniquest day 1-5 to statement level 1-3 for variety."""
    return ((day - 1) % 3) + 1


async def get_statement_for_miniquest(
    weapon: str, day: int, redis_conn=None
) -> Statement:
    """Get a random statement for miniquest day 1-5. Uses level based on day."""
    level = _miniquest_level(day)
    stmts = await load_statements(weapon, redis_conn)
    pool = stmts.get(level, [])
    if not pool:
        all_pool = []
        for lst in stmts.values():
            all_pool.extend(lst)
        pool = all_pool
    if not pool:
        return FALLBACK_STATEMENT
    return random.choice(pool)


async def get_statement_for_round(
    weapon: str, round_num: int, redis_conn=None
) -> Statement:
    stmts = await load_statements(weapon, redis_conn)
    pool = stmts.get(round_num, [])
    if not pool:
        logger.warning("No statements for weapon=%s round=%d, using fallback", weapon, round_num)
        return Statement(
            text=FALLBACK_STATEMENT.text,
            is_truth=FALLBACK_STATEMENT.is_truth,
            wisdom_prompt=FALLBACK_STATEMENT.wisdom_prompt,
            level=round_num,
        )
    return random.choice(pool)


def format_statement(statement: Statement, round_num: int, score: int) -> str:
    round_name = ROUND_NAMES.get(round_num, f"Раунд {round_num}")
    progress = "🟢" * score + "⚫" * (round_num - 1 - score)
    progress_line = f"Раунд {round_num}/3 | Артефакты: {score}" if round_num > 1 else f"Раунд {round_num}/3"
    return (
        f"⚔️ <b>{round_name}</b>\n"
        f"{'─' * 20}\n"
        f"📊 {progress_line} {progress}\n\n"
        f"📜 <b>Утверждение:</b>\n"
        f"<i>«{statement.text}»</i>\n\n"
        f"💡 <b>Подсказка от мудреца:</b>\n"
        f"<i>{statement.wisdom_prompt}</i>\n\n"
        "Это <b>ПРАВДА</b> или <b>ЛОЖЬ</b>?"
    )


def format_round_result(
    is_correct: bool,
    round_num: int,
    score: int,
    statement: Statement,
) -> str:
    """Build the rich post-answer message with Hydra head text."""
    if is_correct:
        head_key = f"head_round{round_num}_cut"
    else:
        head_key = f"head_round{round_num}_alive"

    from utils.content_manager import ContentManager
    head_text = ContentManager.get(head_key)

    truth_label = "✓ ПРАВДА" if statement.is_truth else "✗ ЛОЖЬ"

    if is_correct:
        return (
            f"✅ <b>ВЕРНО!</b>\n\n"
            f"Утверждение: <b>{truth_label}</b>\n\n"
            f"{head_text}\n\n"
            f"Артефакты: <b>{score}/3</b>"
        )
    return (
        f"❌ <b>Неверно!</b>\n\n"
        f"Утверждение: <b>{truth_label}</b>\n\n"
        f"{head_text}\n\n"
        f"Артефакты: <b>{score}/3</b>"
    )
