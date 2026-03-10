import asyncio
import json

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from bot import POOL_KEY, REDIS_CONN_KEY, handle_health


class _PoolConn:
    async def fetchval(self, _query: str) -> int:
        return 1


class _PoolAcquireCtx:
    async def __aenter__(self) -> _PoolConn:
        return _PoolConn()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _PoolOk:
    def acquire(self, timeout: int = 2) -> _PoolAcquireCtx:
        return _PoolAcquireCtx()


class _RedisOk:
    async def ping(self) -> bool:
        return True


class _RedisFail:
    async def ping(self) -> bool:
        raise RuntimeError("redis down")


def _response_json(response: web.Response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def test_health_ok_when_db_and_redis_respond() -> None:
    app = web.Application()
    app[POOL_KEY] = _PoolOk()
    app[REDIS_CONN_KEY] = _RedisOk()
    request = make_mocked_request("GET", "/health", app=app)

    response = asyncio.run(handle_health(request))
    payload = _response_json(response)

    assert response.status == 200
    assert payload["status"] == "ok"
    assert payload["postgres"] == "ok"
    assert payload["redis"] == "ok"


def test_health_degraded_when_redis_fails() -> None:
    app = web.Application()
    app[POOL_KEY] = _PoolOk()
    app[REDIS_CONN_KEY] = _RedisFail()
    request = make_mocked_request("GET", "/health", app=app)

    response = asyncio.run(handle_health(request))
    payload = _response_json(response)

    assert response.status == 503
    assert payload["status"] == "degraded"
    assert payload["postgres"] == "ok"
    assert str(payload["redis"]).startswith("error:")
