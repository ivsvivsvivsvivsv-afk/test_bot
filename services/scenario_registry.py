"""
Scenario registry for multi-client transport adapters.

Each client channel can run its own funnel scenario and A/B variants
without changing core business services.
Scenario → bundle_id mapping for ContentRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioSpec:
    ab_variants: tuple[str, ...]
    bundle_id: str


@dataclass(frozen=True)
class ScenarioContext:
    client_type: str
    scenario_id: str
    ab_variant: str
    bundle_id: str


_SCENARIOS: dict[str, dict[str, ScenarioSpec]] = {
    "telegram": {
        "tg_main_quest": ScenarioSpec(("a", "b"), "default"),
        "tg_short_quest": ScenarioSpec(("a",), "default"),
    },
    "vk": {
        "vk_main_quest": ScenarioSpec(("a", "b"), "default"),
        "vk_main_quest_markets": ScenarioSpec(("a", "b"), "markets"),
        "vk_warmup_quest": ScenarioSpec(("a",), "default"),
    },
    "web": {
        "web_l1": ScenarioSpec(("a", "b"), "default"),
        "web_l2": ScenarioSpec(("a", "b", "c"), "default"),
        "web_l1_markets": ScenarioSpec(("a", "b"), "markets"),
        "web_l2_markets": ScenarioSpec(("a", "b"), "markets"),
    },
}


def _normalize_client_type(raw: str | None) -> str:
    if not raw:
        return "telegram"
    value = raw.strip().lower()
    if value in {"tg", "telegram_bot"}:
        return "telegram"
    if value in {"vkbot", "vkontakte"}:
        return "vk"
    if value in {"site", "landing"}:
        return "web"
    return value


def resolve_scenario_context(
    *,
    client_type: str | None,
    scenario_id: str | None,
    ab_variant: str | None,
) -> ScenarioContext:
    """
    Resolve and validate scenario context for a client channel.
    Falls back to deterministic defaults for unknown values.
    Returns bundle_id for ContentRegistry.
    """
    normalized_client = _normalize_client_type(client_type)
    scenarios = _SCENARIOS.get(normalized_client) or _SCENARIOS["telegram"]

    resolved_scenario = (scenario_id or "").strip().lower()
    if resolved_scenario not in scenarios:
        resolved_scenario = next(iter(scenarios.keys()))

    spec = scenarios[resolved_scenario]
    allowed_variants = spec.ab_variants
    resolved_variant = (ab_variant or "").strip().lower() or allowed_variants[0]
    if resolved_variant not in allowed_variants:
        resolved_variant = allowed_variants[0]

    return ScenarioContext(
        client_type=normalized_client,
        scenario_id=resolved_scenario,
        ab_variant=resolved_variant,
        bundle_id=spec.bundle_id,
    )


def get_scenario_ids_for_bundle(bundle_id: str) -> list[str]:
    """Return scenario_ids that map to the given bundle_id."""
    result: list[str] = []
    for channel_scenarios in _SCENARIOS.values():
        for sid, spec in channel_scenarios.items():
            if spec.bundle_id == bundle_id:
                result.append(sid)
    return sorted(set(result))


def get_vk_scenario_ids() -> list[str]:
    """Return allowed VK scenario_ids for vk/switch API."""
    return list(_SCENARIOS.get("vk", {}).keys())

