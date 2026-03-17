from utils.tracking_links import build_tracked_url, detect_client_channel


def test_detect_client_channel_by_source() -> None:
    assert detect_client_channel("telegram_ads") == "telegram"
    assert detect_client_channel("vk_target") == "vk"
    assert detect_client_channel("web_landing") == "web"
    assert detect_client_channel("custom_partner") == "other"
    assert detect_client_channel(None) == "unknown"


def test_build_tracked_url_keeps_existing_query() -> None:
    url = build_tracked_url(
        "https://sandbox.neurounit.fun/l2?foo=bar",
        utm_source="telegram",
        utm_medium="bot",
        utm_campaign="quest_workshop",
        utm_content="user_123",
    )
    assert "foo=bar" in url
    assert "utm_source=telegram" in url
    assert "utm_medium=bot" in url
    assert "utm_campaign=quest_workshop" in url
    assert "utm_content=user_123" in url
