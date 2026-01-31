from aiogram import Bot
from config import ADMIN_IDS
from texts import ADMIN_TEMPLATES, WEAPON_LABELS
from typing import Optional


async def notify_admin(bot: Bot, text: str):
    if not ADMIN_IDS:
        return
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


def _weapon_label(weapon: Optional[str], other_sphere: Optional[str]):
    if not weapon:
        return "—"
    if weapon == "other":
        return other_sphere or WEAPON_LABELS.get("other", "Другая сфера")
    return WEAPON_LABELS.get(weapon, weapon)


def build_lead_workshop(user: dict, actions: str, duration: str):
    tpl = ADMIN_TEMPLATES["lead_workshop"]
    return tpl.format(
        first_name=user.get("first_name") or "—",
        username=user.get("username") or "нет",
        phone=user.get("phone") or "—",
        email=user.get("email") or "—",
        user_class=user.get("player_class") or "—",
        user_weapon=_weapon_label(user.get("weapon"), user.get("other_sphere")),
        score=user.get("score") or 0,
        actions=actions,
        duration=duration,
    )


def build_lead_arena(user: dict, timestamp: str):
    tpl = ADMIN_TEMPLATES["lead_arena"]
    return tpl.format(
        first_name=user.get("first_name") or "—",
        username=user.get("username") or "нет",
        phone=user.get("phone") or "—",
        email=user.get("email") or "—",
        timestamp=timestamp,
    )


def build_prize_candidate(user: dict):
    tpl = ADMIN_TEMPLATES["prize_candidate"]
    return tpl.format(
        first_name=user.get("first_name") or "—",
        username=user.get("username") or "нет",
        score=user.get("score") or 0,
    )
