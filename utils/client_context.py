"""
Parse incoming transport payload into normalized attribution context.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs


@dataclass(frozen=True)
class StartPayloadContext:
    utm_source: str
    client_type: str | None
    scenario_id: str | None
    ab_variant: str | None


def parse_start_payload(raw_payload: str | None) -> StartPayloadContext:
    """
    Accepts plain deep-link token or query-like string:
    - "utm_tiktok"
    - "utm_source=vk_ads&client=vk&scenario=vk_main_quest&ab=b"
    """
    payload = (raw_payload or "").strip()
    if not payload:
        return StartPayloadContext(
            utm_source="telegram_organic",
            client_type="telegram",
            scenario_id=None,
            ab_variant=None,
        )

    if "=" not in payload:
        return StartPayloadContext(
            utm_source=payload.lower(),
            client_type="telegram",
            scenario_id=None,
            ab_variant=None,
        )

    parsed = parse_qs(payload, keep_blank_values=False)
    utm_source = (parsed.get("utm_source", ["telegram_organic"])[0] or "telegram_organic").strip().lower()
    client_type = (parsed.get("client", [None])[0] or None)
    scenario_id = (parsed.get("scenario", [None])[0] or None)
    ab_variant = (parsed.get("ab", [None])[0] or None)
    return StartPayloadContext(
        utm_source=utm_source,
        client_type=client_type,
        scenario_id=scenario_id,
        ab_variant=ab_variant,
    )

