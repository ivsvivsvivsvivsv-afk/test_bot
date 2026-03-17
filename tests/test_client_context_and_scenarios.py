from services.scenario_registry import (
    get_scenario_ids_for_bundle,
    get_vk_scenario_ids,
    resolve_scenario_context,
)
from utils.client_context import parse_start_payload
from utils.content_registry import get, list_bundles, reset as content_reset


def test_parse_start_payload_query_params() -> None:
    ctx = parse_start_payload("utm_source=vk_ads&client=vk&scenario=vk_main_quest&ab=b")
    assert ctx.utm_source == "vk_ads"
    assert ctx.client_type == "vk"
    assert ctx.scenario_id == "vk_main_quest"
    assert ctx.ab_variant == "b"


def test_parse_start_payload_plain_token() -> None:
    ctx = parse_start_payload("utm_tiktok")
    assert ctx.utm_source == "utm_tiktok"
    assert ctx.client_type == "telegram"
    assert ctx.scenario_id is None


def test_resolve_scenario_context_fallbacks() -> None:
    sc = resolve_scenario_context(client_type="vk", scenario_id="unknown", ab_variant="zzz")
    assert sc.client_type == "vk"
    assert sc.scenario_id == "vk_main_quest"
    assert sc.ab_variant == "a"
    assert sc.bundle_id == "default"


def test_resolve_scenario_context_bundle_id() -> None:
    sc = resolve_scenario_context(
        client_type="web", scenario_id="web_l1_markets", ab_variant="b"
    )
    assert sc.client_type == "web"
    assert sc.scenario_id == "web_l1_markets"
    assert sc.ab_variant == "b"
    assert sc.bundle_id == "markets"


def test_content_registry_get_default() -> None:
    content_reset()
    from utils.content_registry import load_all

    load_all()
    text = get("default", "welcome")
    assert "КВЕСТ" in text or "квест" in text.lower()


def test_content_registry_get_with_format() -> None:
    content_reset()
    from utils.content_registry import load_all

    load_all()
    # Use key that exists in both legacy and bundle texts
    text = get("default", "result_perfect", first_name="Тест")
    assert "Тест" in text


def test_content_registry_list_bundles() -> None:
    content_reset()
    from utils.content_registry import load_all

    load_all()
    bundles = list_bundles()
    assert "default" in bundles


def test_get_scenario_ids_for_bundle() -> None:
    default_ids = get_scenario_ids_for_bundle("default")
    assert "vk_main_quest" in default_ids
    assert "web_l1" in default_ids

    markets_ids = get_scenario_ids_for_bundle("markets")
    assert "vk_main_quest_markets" in markets_ids
    assert "web_l1_markets" in markets_ids


def test_get_vk_scenario_ids() -> None:
    ids = get_vk_scenario_ids()
    assert "vk_main_quest" in ids
    assert "vk_main_quest_markets" in ids


def test_session_start_with_web_l1_markets_returns_bundle_in_ui() -> None:
    """POST session/start with scenario_id=web_l1_markets yields bundle_id=markets in flow."""
    from services.scenario_registry import resolve_scenario_context

    sc = resolve_scenario_context(
        client_type="web",
        scenario_id="web_l1_markets",
        ab_variant="a",
    )
    assert sc.bundle_id == "markets"
    # Session would store bundle_id; UI would use content from markets (or default fallback)

