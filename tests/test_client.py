import asyncio

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import (
    BASE_URL,
    BROWSER_HEADERS,
    ComunioClient,
    default_headers,
)
from comunio_mcp.config import Settings

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


class FakeApi:
    """Answers the login endpoint and one data endpoint."""

    def __init__(self, *, unauthorized_calls: int = 0) -> None:
        self.calls: list[httpx2.Request] = []
        self.unauthorized_calls = unauthorized_calls
        self._logins = 0

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login":
            self._logins += 1
            return httpx2.Response(
                200,
                json={
                    "access_token": f"access-{self._logins}",
                    "expires_in": 1800,
                    "token_type": "Bearer",
                    "scope": "",
                    "refresh_token": f"refresh-{self._logins}",
                },
            )

        self.calls.append(request)
        if len(self.calls) <= self.unauthorized_calls:
            return httpx2.Response(401, json={"error": "expired"})
        return httpx2.Response(200, json={"ok": True})


def _run(handler: FakeApi, body):
    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), headers=default_headers(SETTINGS)
    )

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(client)

    return asyncio.run(run())


def test_get_sends_the_bearer_token_and_returns_json():
    handler = FakeApi()

    data = _run(handler, lambda client: client.get("/squad"))

    assert data == {"ok": True}
    assert str(handler.calls[0].url) == f"{BASE_URL}/squad"
    assert handler.calls[0].headers["authorization"] == "Bearer access-1"


def test_requests_reproduce_the_captured_browser_headers():
    # The captured web-app request is the only one we know Comunio accepts. Trimming
    # this set is an untested change against a private backend, so it is pinned here.
    handler = FakeApi()

    _run(handler, lambda client: client.get("/squad"))

    headers = handler.calls[0].headers
    for name, value in BROWSER_HEADERS.items():
        assert headers[name] == value, name
    assert headers["x-timezone"] == "Europe/Madrid"
    assert headers["user-agent"] == SETTINGS.user_agent
    assert headers["user-agent"].startswith("Mozilla/5.0")


def test_a_401_triggers_one_reauthenticated_retry():
    handler = FakeApi(unauthorized_calls=1)

    data = _run(handler, lambda client: client.get("/squad"))

    assert data == {"ok": True}
    assert len(handler.calls) == 2
    # The retry carries a token obtained after the cached one was dropped.
    assert handler.calls[0].headers["authorization"] == "Bearer access-1"
    assert handler.calls[1].headers["authorization"] == "Bearer access-2"


def test_a_persistent_401_is_raised_rather_than_retried_forever():
    handler = FakeApi(unauthorized_calls=99)

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda client: client.get("/squad"))

    assert len(handler.calls) == 2
