"""
Helpers for channel-aware landing URLs and attribution parsing.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def detect_client_channel(utm_source: str | None) -> str:
    """
    Derive a normalized client channel from utm_source.
    """
    if not utm_source:
        return "unknown"
    source = utm_source.strip().lower()
    if source.startswith(("tg", "telegram")):
        return "telegram"
    if source.startswith(("vk", "vkontakte")):
        return "vk"
    if source.startswith(("web", "site", "landing", "instagram", "insta")):
        return "web"
    return "other"


def build_tracked_url(
    base_url: str,
    *,
    utm_source: str | None,
    utm_medium: str,
    utm_campaign: str,
    utm_content: str | None = None,
) -> str:
    """
    Build URL with deterministic UTM tags while preserving existing query params.
    """
    parts = urlsplit(base_url.strip())
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params["utm_source"] = (utm_source or "unknown").strip().lower() or "unknown"
    query_params["utm_medium"] = utm_medium.strip().lower()
    query_params["utm_campaign"] = utm_campaign.strip().lower()
    if utm_content:
        query_params["utm_content"] = utm_content.strip().lower()
    new_query = urlencode(query_params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

