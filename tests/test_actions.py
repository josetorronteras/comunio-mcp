import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.actions import list_on_market, parse_listing_result
from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")

OK_RESPONSE = {"status": "OK", "notPlaced": [], "purchasePrices": {"3354": 0}, "remaining": 36}


class FakeApi:
    """Answers login, the index, and the addplayer endpoint."""

    def __init__(self, *, add_response=None, add_status=200, unauthorized_first=False) -> None:
        self.writes: list[httpx2.Request] = []
        self.add_response = OK_RESPONSE if add_response is None else add_response
        self.add_status = add_status
        self.unauthorized_first = unauthorized_first
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
        if request.url.path == "/":
            return httpx2.Response(
                200,
                json={
                    "user": {"id": USER_ID},
                    "community": {"id": COMMUNITY_ID},
                    "_links": {
                        "game:exchangemarket": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/exchangemarket"
                        }
                    },
                },
            )

        self.writes.append(request)
        if self.unauthorized_first and len(self.writes) == 1:
            return httpx2.Response(401, json={"error": "expired"})
        return httpx2.Response(self.add_status, json=self.add_response)


def _run(handler: FakeApi, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            auth = ComunioAuth(http, SETTINGS)
            client = ComunioClient(http, auth)
            return await body(Session(client), client)

    return asyncio.run(run())


def test_a_player_is_listed_with_the_documented_body():
    handler = FakeApi()

    result = _run(handler, lambda s, c: list_on_market(s, c, 3354, 370_000))

    assert len(handler.writes) == 1
    request = handler.writes[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/exchangemarket/addplayer")
    # `tradableId`, camelCase, nested in items[] — this endpoint's own spelling.
    assert json.loads(request.content) == {"items": [{"tradableId": 3354, "price": 370_000}]}
    assert result.placed == [3354]
    assert result.rejected == []
    assert result.remaining == 36


def test_a_write_is_never_retried_after_a_401():
    # A retry would list the player twice if the first request had reached Comunio and
    # only its response was lost.
    handler = FakeApi(unauthorized_first=True)

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: list_on_market(s, c, 3354, 370_000))

    assert len(handler.writes) == 1


def test_a_rejected_player_is_reported_as_rejected():
    # The outer status says OK while the player was refused. Trusting it would report a
    # listing that never happened.
    handler = FakeApi(add_response={"status": "OK", "notPlaced": [3354], "remaining": 36})

    result = _run(handler, lambda s, c: list_on_market(s, c, 3354, 370_000))

    assert result.placed == []
    assert result.rejected == [3354]


def test_rejections_are_read_from_objects_too():
    # `notPlaced` has only ever been seen empty, so its element shape is a guess.
    result = parse_listing_result(
        {"status": "OK", "notPlaced": [{"tradableId": 99}]}, requested=[99, 100]
    )

    assert result.rejected == [99]
    assert result.placed == [100]


def test_an_http_error_is_raised_rather_than_swallowed():
    handler = FakeApi(add_status=500, add_response={"error": "boom"})

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: list_on_market(s, c, 3354, 370_000))


def test_a_price_of_zero_is_refused_before_anything_is_sent():
    handler = FakeApi()

    with pytest.raises(ValueError):
        _run(handler, lambda s, c: list_on_market(s, c, 3354, 0))

    assert handler.writes == []
