"""
HTTP endpoints for web media manifest.
"""

from __future__ import annotations

from aiohttp import web

from utils.web_media import load_manifest


async def get_web_media_manifest(_request: web.Request) -> web.Response:
    """
    Public manifest for web client media mapping.
    Cached in-process via utils.web_media.load_manifest().
    """
    return web.json_response(load_manifest(force=False))


def register_web_media_routes(app: web.Application) -> None:
    app.router.add_get("/api/web/content/media-manifest", get_web_media_manifest)
