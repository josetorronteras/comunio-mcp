import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from comunio_mcp.comunio.auth import EXPIRY_MARGIN, AuthError, ComunioAuth, Token
from comunio_mcp.comunio.client import BROWSER_HEADERS, default_headers
from comunio_mcp.config import Settings

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


def _payload(access: str, refresh: str, expires_in: int = 1800) -> dict:
    return {
        "access_token": access,
        "expires_in": expires_in,
        "token_type": "Bearer",
        "scope": "",
        "refresh_token": refresh,
    }


class FakeLogin:
    """Stands in for POST https://api.comunio.es/login."""

    def __init__(self, *, expires_in: int = 1800) -> None:
        self.requests: list[dict] = []
        self.expires_in = expires_in
        self.reject_refresh = False
        self._counter = 0

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append(
            {
                "body": body,
                "authorization": request.headers.get("authorization"),
                "headers": request.headers,
                "is_refresh": "refresh_token" in body,
            }
        )

        if "refresh_token" in body and self.reject_refresh:
            return httpx2.Response(401, json={"error": "invalid_grant"})

        self._counter += 1
        n = self._counter
        return httpx2.Response(
            200, json=_payload(f"access-{n}", f"refresh-{n}", expires_in=self.expires_in)
        )


def _auth(handler: FakeLogin) -> tuple[ComunioAuth, httpx2.AsyncClient]:
    http = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), headers=default_headers(SETTINGS)
    )
    return ComunioAuth(http, SETTINGS), http


async def _with_client(handler: FakeLogin, body):
    auth, http = _auth(handler)
    async with http:
        return await body(auth)


def test_first_call_logs_in_with_credentials_and_tzoffset():
    handler = FakeLogin()

    token = asyncio.run(_with_client(handler, lambda auth: auth.access_token()))

    assert token == "access-1"
    assert len(handler.requests) == 1
    sent = handler.requests[0]["body"]
    assert sent["username"] == "manager"
    assert sent["password"] == "s3cret"
    assert sent["tzoffset"] == SETTINGS.tz_offset_hours()


def test_login_carries_the_captured_browser_headers():
    handler = FakeLogin()

    asyncio.run(_with_client(handler, lambda auth: auth.access_token()))

    headers = handler.requests[0]["headers"]
    for name, value in BROWSER_HEADERS.items():
        assert headers[name] == value, name
    assert headers["user-agent"].startswith("Mozilla/5.0")


def test_valid_token_is_reused_without_hitting_the_network():
    handler = FakeLogin()

    async def body(auth):
        return [await auth.access_token(), await auth.access_token(), await auth.access_token()]

    tokens = asyncio.run(_with_client(handler, body))

    assert tokens == ["access-1", "access-1", "access-1"]
    assert len(handler.requests) == 1


def test_expired_token_is_refreshed_with_the_rotated_refresh_token():
    # Shorter than the safety margin, so the very next call considers it stale.
    handler = FakeLogin(expires_in=int(EXPIRY_MARGIN.total_seconds()) - 1)

    async def body(auth):
        return [await auth.access_token(), await auth.access_token()]

    tokens = asyncio.run(_with_client(handler, body))

    assert tokens == ["access-1", "access-2"]
    assert handler.requests[1]["is_refresh"] is True
    assert handler.requests[1]["body"]["refresh_token"] == "refresh-1"
    assert handler.requests[1]["authorization"] == "Bearer access-1"


def test_rejected_refresh_falls_back_to_a_full_login():
    handler = FakeLogin(expires_in=int(EXPIRY_MARGIN.total_seconds()) - 1)
    handler.reject_refresh = True

    async def body(auth):
        return [await auth.access_token(), await auth.access_token()]

    tokens = asyncio.run(_with_client(handler, body))

    assert tokens == ["access-1", "access-2"]
    assert [r["is_refresh"] for r in handler.requests] == [False, True, False]


def test_forget_forces_a_fresh_login():
    handler = FakeLogin()

    async def body(auth):
        first = await auth.access_token()
        auth.forget()
        return [first, await auth.access_token()]

    tokens = asyncio.run(_with_client(handler, body))

    assert tokens == ["access-1", "access-2"]
    assert [r["is_refresh"] for r in handler.requests] == [False, False]


def test_http_error_raises_auth_error_without_leaking_the_body():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(403, json={"password": "s3cret"})

    async def body(auth):
        return await auth.access_token()

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    auth = ComunioAuth(http, SETTINGS)

    async def run():
        async with http:
            with pytest.raises(AuthError) as excinfo:
                await auth.access_token()
            return str(excinfo.value)

    message = asyncio.run(run())

    assert "403" in message
    assert "s3cret" not in message


def test_malformed_payload_is_rejected():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "a"})

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    auth = ComunioAuth(http, SETTINGS)

    async def run():
        async with http:
            with pytest.raises(AuthError):
                await auth.access_token()

    asyncio.run(run())


def test_token_usability_respects_the_safety_margin():
    now = datetime.now(UTC)
    token = Token("a", "r", expires_at=now + EXPIRY_MARGIN / 2)

    assert token.is_usable(now) is False
    assert Token("a", "r", expires_at=now + timedelta(hours=1)).is_usable(now) is True
