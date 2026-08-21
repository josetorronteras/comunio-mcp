"""Every tool, entered the way a client enters it: through `mcp.call_tool`.

The rest of the suite drives the functions under `comunio/` directly, and `test_server`
reads the annotations. Between the two sits the wrapper each `tools/*.py` registers —
pulling `AppContext` out of the request context and resolving the session and the client
— which nothing else executes. These tests go in through the same door a real MCP client
uses, so that wiring cannot rot unnoticed.

Two passes over the same table:

* **Wired up.** Every tool reaches the fake API and comes back without an error.
* **No credentials.** Every tool fails with the message that says how to fix it, and
  **nothing leaves the process** — asserted on the request log, not on the wording.
"""

import asyncio

import httpx2
import pytest
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import Settings
from comunio_mcp.context import AppContext
from comunio_mcp.server import mcp
from tests.conftest import (
    COMMUNITY_ID,
    INDEX_RESPONSE,
    MARKET_RESPONSE,
    NEWS_RESPONSE,
    OFFERS_HISTORY_RESPONSE,
    OFFERS_RESPONSE,
    PLAYER_RESPONSE,
    SQUAD_RESPONSE,
    STANDINGS_RESPONSE,
    USER_ID,
    WATCHLIST_RESPONSE,
)

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")

PROTOCOL_VERSION = "2026-07-28"

#: Ids picked from the fixtures for what each tool needs:
#: 1001 is on the market and owned by Comunio, so it can be bid on; 9000001 is an offer
#: *for* one of the manager's players, so it can be accepted; 9000003 is a bid the
#: manager made, so it can be changed or withdrawn.
MARKET_PLAYER = 1001
INCOMING_OFFER = 9000001
OUTGOING_OFFER = 9000003
OWN_PLAYER = 1005
DETAIL_PLAYER = 1400
WATCHED_PLAYER = 6001

_BASE = f"https://api.comunio.es/communities/{COMMUNITY_ID}/users/{USER_ID}"

#: The index fixture carries the account state `get_account` reads and a few links;
#: these are the rest of the routes the other tools resolve through `session.link`.
#: `game:squad` and `game:tradable` come from the fixture still holding their
#: `:placeholder` segments, so the resolver is exercised too.
INDEX = {
    **INDEX_RESPONSE,
    "_links": {
        **INDEX_RESPONSE["_links"],
        "game:standings": {"href": f"https://api.comunio.es/communities/{COMMUNITY_ID}/standings"},
        "game:exchangemarket": {"href": f"{_BASE}/exchangemarket"},
        "game:readOffers": {"href": f"{_BASE}/offers"},
        "game:readOffersHistory": {"href": f"{_BASE}/offershistory"},
        "game:news": {"href": f"https://api.comunio.es/communities/{COMMUNITY_ID}/news"},
        "game:watchlist": {"href": f"{_BASE}/watchlist"},
    },
}

#: What the market and offer endpoints answer a write with. The per-item status is the
#: one that matters; the outer one only says the request was processed.
WRITE_OK = {"status": "OK", "notPlaced": [], "remaining": 36}
OFFER_OK = {"response": [{"status": "OK", "offerid": 9000009, "processImmediately": True}]}


class FakeApi:
    """Answers login, the index and every endpoint the tools reach.

    Records every request but the login, so a test can assert that a refused call sent
    nothing at all. The index counts: `get_account` reads it and nothing else.
    """

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path

        if path == "/login":
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

        self.requests.append(request)

        if path == "/":
            return httpx2.Response(200, json=INDEX)
        return self._answer(path, request.method)

    def _answer(self, path: str, method: str) -> httpx2.Response:
        # Checked before `/players/`, which the watchlist write path also ends with.
        if "/watchlist" in path:
            if method == "GET":
                return httpx2.Response(200, json=WATCHLIST_RESPONSE)
            return httpx2.Response(200, json={"status": "OK"})
        if path.endswith("/exchangemarket"):
            return httpx2.Response(200, json=MARKET_RESPONSE)
        if path.endswith("/recommendedprice"):
            # This one answers with a bare boolean, unlike every other action.
            return httpx2.Response(200, json=True)
        if "/exchangemarket/" in path:
            return httpx2.Response(200, json=WRITE_OK)
        if path.endswith("/offershistory"):
            return httpx2.Response(200, json=OFFERS_HISTORY_RESPONSE)
        if path.endswith("/offers"):
            if method == "GET":
                return httpx2.Response(200, json=OFFERS_RESPONSE)
            return httpx2.Response(200, json=OFFER_OK)
        if "/offers/" in path:
            return httpx2.Response(200, json={"status": "OK"})
        if path.endswith("/squad"):
            return httpx2.Response(200, json=SQUAD_RESPONSE)
        if path.endswith("/standings"):
            return httpx2.Response(200, json=STANDINGS_RESPONSE)
        if path.endswith("/news"):
            return httpx2.Response(200, json=NEWS_RESPONSE)
        if path.endswith("/lineup"):
            return httpx2.Response(200, json={"status": "OK"})
        if "/players/" in path:
            return httpx2.Response(200, json=PLAYER_RESPONSE)

        raise AssertionError(f"unexpected request: {method} {path}")


#: Every registered tool with arguments that should get through. Kept as one table so a
#: new tool that is not listed here fails `test_the_table_covers_every_tool`.
TOOL_CALLS: list[tuple[str, dict]] = [
    ("get_account", {}),
    ("get_squad", {}),
    ("get_player", {"player_id": DETAIL_PLAYER}),
    ("get_standings", {}),
    ("get_market", {}),
    ("get_offers", {}),
    ("get_transfers", {}),
    ("get_news", {}),
    ("get_watchlist", {}),
    ("list_player_on_market", {"player_id": OWN_PLAYER, "price": 370_000}),
    ("unlist_player_from_market", {"player_id": OWN_PLAYER}),
    ("change_listing_price", {"player_id": OWN_PLAYER, "price": 420_000}),
    ("place_bid", {"player_id": MARKET_PLAYER, "price": 2_700_000}),
    ("change_bid", {"offer_id": OUTGOING_OFFER, "price": 1_300_000}),
    ("withdraw_bid", {"offer_id": OUTGOING_OFFER}),
    ("accept_offer", {"offer_id": INCOMING_OFFER}),
    (
        "set_lineup",
        {
            "tactic": "442",
            "keeper": 1001,
            "defenders": [1003, 1004, 1005],
            "midfielders": [1006, 1007],
            "strikers": [1008],
        },
    ),
    ("watch_player", {"player_id": WATCHED_PLAYER}),
    ("unwatch_player", {"player_id": WATCHED_PLAYER}),
]


def _context(app: AppContext) -> Context:
    """The request context a tool call arrives with, carrying `app` as the lifespan.

    `session` is the connection back to the client, used only for logging and progress;
    no tool here touches it.
    """
    return Context(
        request_context=ServerRequestContext(
            session=None,
            lifespan_context=app,
            protocol_version=PROTOCOL_VERSION,
            method="tools/call",
        )
    )


def _call(name: str, arguments: dict, app: AppContext):
    return asyncio.run(mcp.call_tool(name, arguments, _context(app)))


def _wired(handler: FakeApi, name: str, arguments: dict):
    """Call a tool against the fake API, wired up as the lifespan would wire it."""
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            app = AppContext(comunio=client, session=Session(client))
            return await mcp.call_tool(name, arguments, _context(app))

    return asyncio.run(run())


def test_the_table_covers_every_tool() -> None:
    # Otherwise a tool added later would quietly go untested by everything below.
    registered = {tool.name for tool in asyncio.run(mcp.list_tools())}

    assert {name for name, _ in TOOL_CALLS} == registered


@pytest.mark.parametrize(("name", "arguments"), TOOL_CALLS, ids=[n for n, _ in TOOL_CALLS])
def test_every_tool_reaches_comunio_through_the_server(name: str, arguments: dict) -> None:
    handler = FakeApi()

    result = _wired(handler, name, arguments)

    assert not result.is_error, result.content
    assert result.structured_content is not None
    assert handler.requests, "the tool answered without ever calling Comunio"


@pytest.mark.parametrize(("name", "arguments"), TOOL_CALLS, ids=[n for n, _ in TOOL_CALLS])
def test_no_tool_calls_out_without_credentials(name: str, arguments: dict) -> None:
    # `lifespan` yields this when COMUNIO_USERNAME and COMUNIO_PASSWORD are missing: the
    # server still starts, and every tool has to fail before it reaches the network.
    handler = FakeApi()

    with pytest.raises(ToolError):
        _call(name, arguments, AppContext(comunio=None, session=None))

    assert handler.requests == []
