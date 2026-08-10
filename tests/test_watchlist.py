import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.watchlist import (
    fetch_watchlist,
    parse_watchlist,
    unwatch_player,
    watch_player,
)
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


class FakeApi:
    def __init__(self, *, watchlist=None, response=None) -> None:
        self.writes: list[httpx2.Request] = []
        self.watchlist = watchlist if watchlist is not None else {"tradables": []}
        self.response = response if response is not None else {"status": "OK"}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login":
            return httpx2.Response(
                200,
                json={
                    "access_token": "a",
                    "expires_in": 1800,
                    "token_type": "Bearer",
                    "scope": "",
                    "refresh_token": "r",
                },
            )
        if request.url.path == "/":
            return httpx2.Response(
                200,
                json={
                    "user": {"id": USER_ID},
                    "community": {"id": COMMUNITY_ID},
                    "_links": {
                        "game:watchlist": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/watchlist"
                        }
                    },
                },
            )
        if request.method == "GET":
            return httpx2.Response(200, json=self.watchlist)

        self.writes.append(request)
        return httpx2.Response(200, json=self.response)


def _run(handler, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(Session(client), client)

    return asyncio.run(run())


def test_an_empty_watchlist_is_the_only_shape_ever_observed():
    handler = FakeApi()

    result = _run(handler, fetch_watchlist)

    assert result.total == 0
    assert result.players == []


def _entry(player_id=3469, name="Delantero Vigilado", owner=None):
    """Shaped exactly like a real entry: flat, and `quotedprice` without a capital P."""
    return {
        "id": player_id,
        "name": name,
        "club": {"id": 5, "name": "Mock FC", "abbreviation": "", "_links": {}},
        "owner": owner,
        "quotedprice": 27_410_000,
        "trend": 1,
        "points": "-",
        "lastPoints": "13",
        "position": "striker",
        "status": "ACTIVE",
        "statusInfo": "",
        "watched": True,
        "disabled": False,
        "hasAcceptedBuyoutClauseOffer": False,
        "_links": {"photo": {"href": "https://api.comunio.es/x/photo"}},
    }


def test_an_entry_is_read_with_the_squads_spelling_of_the_price():
    # This endpoint sends `quotedprice`, like the squad — not the market's `quotedPrice`.
    result = parse_watchlist({"tradables": [_entry()]})

    player = result.players[0]
    assert (player.id, player.name, player.club) == (3469, "Delantero Vigilado", "Mock FC")
    assert player.quoted_price == 27_410_000
    assert player.trend == 1


def test_the_usual_no_data_encodings_are_normalised():
    result = parse_watchlist({"tradables": [_entry()]})

    player = result.players[0]
    assert player.points is None      # "-"
    assert player.last_points == 13   # "13"
    assert player.status_info is None  # ""


def test_a_player_nobody_owns_is_flagged():
    # `owner` is null for an unowned player, who can only ever arrive via the market.
    result = parse_watchlist({"tradables": [_entry(owner=None)]})

    assert result.players[0].unowned is True
    assert result.players[0].owner is None
    assert result.unowned == 1


def test_a_player_held_by_a_rival_names_them():
    result = parse_watchlist(
        {"tradables": [_entry(owner={"id": 30000001, "name": "Rival Uno"})]}
    )

    player = result.players[0]
    assert player.unowned is False
    assert (player.owner, player.owner_id) == ("Rival Uno", 30000001)
    assert result.unowned == 0


def test_link_clutter_is_dropped():
    serialised = json.dumps(
        parse_watchlist({"tradables": [_entry()]}).model_dump(), ensure_ascii=False
    )

    for noise in ("_links", "photo", "hasAcceptedBuyoutClauseOffer", "abbreviation"):
        assert noise not in serialised


def test_watching_a_player_posts_an_empty_body():
    handler = FakeApi(response={"status": "OK"})

    result = _run(handler, lambda s, c: watch_player(s, c, 3469))

    request = handler.writes[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/watchlist/players/3469")
    assert json.loads(request.content) == {}
    assert result.ok is True
    assert result.watching is True


def test_unwatching_sends_a_delete_that_still_carries_a_body():
    # A DELETE with a body is unusual, and Comunio wants one.
    handler = FakeApi()

    result = _run(handler, lambda s, c: unwatch_player(s, c, 2565))

    request = handler.writes[0]
    assert request.method == "DELETE"
    assert request.url.path.endswith("/watchlist/players/2565")
    assert json.loads(request.content) == {}
    assert result.ok is True
    assert result.watching is False


def test_a_bare_true_would_also_count_as_success():
    # `set_asking_price` answers that way, so it is not out of character here.
    handler = FakeApi(response=True)

    result = _run(handler, lambda s, c: watch_player(s, c, 3469))

    assert result.ok is True


def test_a_non_ok_status_is_a_failure():
    handler = FakeApi(response={"status": "ERROR"})

    result = _run(handler, lambda s, c: watch_player(s, c, 3469))

    assert result.ok is False


def test_watchlist_writes_are_not_retried_after_a_401():
    class Unauthorized(FakeApi):
        def __call__(self, request):
            # Login is a POST too, so it has to be let through or authentication fails
            # before the write is ever attempted.
            if request.url.path != "/login" and request.method in ("POST", "DELETE"):
                self.writes.append(request)
                return httpx2.Response(401, json={"error": "expired"})
            return super().__call__(request)

    handler = Unauthorized()

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: watch_player(s, c, 3469))

    assert len(handler.writes) == 1
