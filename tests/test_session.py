import asyncio

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session, SessionError
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


class FakeApi:
    def __init__(self, index: dict) -> None:
        self.index = index
        self.index_calls = 0

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login":
            return httpx2.Response(
                200,
                json={
                    "access_token": "access",
                    "expires_in": 1800,
                    "token_type": "Bearer",
                    "scope": "",
                    "refresh_token": "refresh",
                },
            )
        self.index_calls += 1
        return httpx2.Response(200, json=self.index)


def _run(index: dict, body):
    handler = FakeApi(index)
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            session = Session(ComunioClient(http, ComunioAuth(http, SETTINGS)))
            return await body(session), handler

    return asyncio.run(run())


def test_info_extracts_ids_and_links(index_response):
    info, _ = _run(index_response, lambda s: s.info())

    assert info.user_id == USER_ID
    assert info.community_id == COMMUNITY_ID
    assert "game:squad" in info.links


def test_routing_is_fetched_once_and_reused(index_response):
    async def body(session):
        await session.info()
        await session.info()
        await session.link("game:squad")
        return None

    _, handler = _run(index_response, body)

    assert handler.index_calls == 1


def test_snapshot_is_always_fetched_fresh(index_response):
    async def body(session):
        await session.snapshot()
        await session.snapshot()
        return None

    _, handler = _run(index_response, body)

    assert handler.index_calls == 2


def test_link_fills_in_the_session_ids(index_response):
    result, _ = _run(index_response, lambda s: s.link("game:squad"))

    assert result == f"https://api.comunio.es/users/{USER_ID}/squad"


def test_link_passes_through_hrefs_that_already_carry_ids(index_response):
    result, _ = _run(index_response, lambda s: s.link("game:lineup"))

    assert result == (
        f"https://api.comunio.es/communities/{COMMUNITY_ID}/users/{USER_ID}/lineup"
    )


def test_link_accepts_extra_parameters(index_response):
    result, _ = _run(index_response, lambda s: s.link("game:tradable", playerId="99"))

    assert result == (
        f"https://api.comunio.es/communities/{COMMUNITY_ID}/users/{USER_ID}/players/99"
    )


def test_link_refuses_to_return_an_unresolved_url(index_response):
    async def body(session):
        with pytest.raises(SessionError) as excinfo:
            await session.link("game:tradable")
        return str(excinfo.value)

    message, _ = _run(index_response, body)

    assert "playerId" in message


def test_unknown_link_is_an_error(index_response):
    async def body(session):
        with pytest.raises(SessionError):
            await session.link("game:doesNotExist")
        return None

    _run(index_response, body)


def test_malformed_index_is_an_error():
    async def body(session):
        with pytest.raises(SessionError):
            await session.info()
        return None

    _run({"unexpected": True}, body)
