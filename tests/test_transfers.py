import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.transfers import _summarise, fetch_transfers, parse_transfers
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, MANAGER_NAME, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


@pytest.fixture
def transfers(offers_history_response):
    return parse_transfers(offers_history_response["items"], me=USER_ID)


def _by_player(transfers, name):
    return next(t for t in transfers if t.player == name)


def test_every_settled_offer_becomes_a_transfer(transfers, offers_history_response):
    assert len(transfers) == len(offers_history_response["items"])


def test_direction_comes_from_owner_and_user_not_from_type(transfers):
    # `type` is a trap: measured over a real league's whole history, SALE appeared 15
    # times on a player moving to Comunio and 13 times on one moving from it. Direction
    # is `tradable.owner` -> `user`, which matched the news feed on 31 of 31 deals.
    bought = _by_player(transfers, "Fichaje Dos")
    sold = _by_player(transfers, "Venta Uno")

    # Both are filed as SALE, and they go opposite ways.
    assert bought.from_computer is True
    assert bought.to_computer is False
    assert sold.from_computer is False
    assert sold.to_computer is True


def test_the_owner_is_the_seller_and_the_user_is_the_buyer(transfers):
    bought = _by_player(transfers, "Fichaje Uno")

    assert bought.from_manager == "Computer"
    assert bought.from_id == 1
    assert bought.to_manager == MANAGER_NAME
    assert bought.to_id == int(USER_ID)


def test_a_deal_between_managers_touches_neither_side_of_comunio(transfers):
    direct = _by_player(transfers, "Traspaso Directo")

    assert direct.from_computer is False
    assert direct.to_computer is False
    assert direct.involves_me is False


def test_the_managers_own_deals_are_marked(transfers):
    mine = [t for t in transfers if t.involves_me]

    assert {t.player for t in mine} == {"Fichaje Uno", "Venta Propia"}


def test_names_are_stripped_on_both_sides(transfers):
    own_sale = _by_player(transfers, "Venta Propia")

    # The player's name arrives padded at both ends, the owner's with a trailing space.
    assert own_sale.from_manager == MANAGER_NAME


def test_what_was_paid_sits_next_to_what_it_was_worth(transfers):
    over = _by_player(transfers, "Fichaje Uno")
    under = _by_player(transfers, "Traspaso Directo")

    # The point of the tool: settled prices, and whether they beat the quote.
    assert over.price == 2_300_000
    assert over.quoted_price == 1_780_000
    assert under.price < under.quoted_price


def test_both_timestamps_survive(transfers):
    sold = _by_player(transfers, "Venta Uno")

    # The news feed only gave the day of the digest; this gives the bid and the settlement.
    assert sold.offered_at.day == 10
    assert sold.settled_at.hour == 6


def test_the_player_arrives_described(transfers):
    injured = _by_player(transfers, "Venta Propia")

    assert injured.position == "striker"
    assert injured.club == "Mock FC"
    assert injured.status == "WEAKENED"


def test_no_photos_logos_or_hrefs_leak_through(transfers):
    serialised = json.dumps([t.model_dump(mode="json") for t in transfers], ensure_ascii=False)

    assert "api.comunio.es" not in serialised
    assert "/photo" not in serialised


def test_the_misleading_type_is_not_exposed(transfers):
    # Carrying a field whose only property is looking meaningful invites the mistake.
    assert not hasattr(transfers[0], "kind")
    assert "SALE" not in json.dumps([t.model_dump(mode="json") for t in transfers])


def test_the_summary_counts_each_kind(transfers):
    summary = _summarise(transfers, me=USER_ID)

    assert summary.total == 5
    assert summary.bought_from_computer == 2
    assert summary.sold_to_computer == 2
    assert summary.between_managers == 1
    assert summary.mine == 2
    assert summary.total_value == sum(t.price for t in transfers)


def test_a_malformed_item_is_skipped():
    assert parse_transfers(["not a dict", None], me=USER_ID) == []


class FakeApi:
    """Answers login, the index and the offer-history endpoint, one page at a time."""

    def __init__(self, pages) -> None:
        self.pages = pages
        self.requested: list[str] = []

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
                        "game:readOffersHistory": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/offers/history"
                        }
                    },
                },
            )

        self.requested.append(str(request.url))
        page = self.pages.pop(0) if self.pages else {"items": [], "hasMore": False}
        return httpx2.Response(200, json=page)


def _run(handler, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(Session(client), client)

    return asyncio.run(run())


def test_it_reads_the_history_link_rather_than_the_news_feed(offers_history_response):
    handler = FakeApi([offers_history_response])

    _run(handler, lambda s, c: fetch_transfers(s, c))

    assert "/offers/history" in handler.requested[0]
    # The old source. Reading it needed twelve requests for what this does in one.
    assert "news" not in handler.requested[0]


def test_the_limit_is_asked_for_rather_than_capped(offers_history_response):
    handler = FakeApi([offers_history_response])

    _run(handler, lambda s, c: fetch_transfers(s, c, limit=100))

    # Unlike the news feed, this endpoint honours the limit, so it is passed straight
    # through instead of being paged around in twenties.
    assert "limit=100" in handler.requested[0]
    assert "offset=0" in handler.requested[0]


def test_one_page_is_enough_when_comunio_says_there_is_no_more(offers_history_response):
    handler = FakeApi([offers_history_response])

    result = _run(handler, lambda s, c: fetch_transfers(s, c, limit=100))

    assert len(handler.requested) == 1
    assert result.has_more is False
    assert result.summary.total == 5


def test_it_pages_on_offset_when_there_is_more(offers_history_response):
    first = {**offers_history_response, "hasMore": True}
    handler = FakeApi([first, offers_history_response])

    result = _run(handler, lambda s, c: fetch_transfers(s, c, limit=10))

    assert len(handler.requested) == 2
    assert "offset=5" in handler.requested[1]
    assert len(result.transfers) == 10


def test_it_stops_at_the_limit_and_says_there_is_more(offers_history_response):
    handler = FakeApi([{**offers_history_response, "hasMore": True}])

    result = _run(handler, lambda s, c: fetch_transfers(s, c, limit=3))

    assert len(result.transfers) == 3
    assert result.has_more is True
