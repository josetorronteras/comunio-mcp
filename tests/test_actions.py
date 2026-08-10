import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.actions import (
    list_on_market,
    parse_listing_result,
    place_bid,
    set_asking_price,
    unlist_from_market,
    withdraw_bid,
)
from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")

OK_RESPONSE = {"status": "OK", "notPlaced": [], "purchasePrices": {"3354": 0}, "remaining": 36}


class FakeApi:
    """Answers login, the index, and the addplayer endpoint."""

    def __init__(
        self,
        *,
        add_response=None,
        add_status=200,
        unauthorized_first=False,
        offers=None,
        market=None,
    ) -> None:
        self.offers = offers or {"credit": 0, "items": []}
        self.market = market or {"items": [], "dailyTransfersProcessed": False}
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
        if request.url.path.endswith("/exchangemarket") and request.method == "GET":
            return httpx2.Response(200, json=self.market)
        if request.url.path.endswith("/offers") and request.method == "GET":
            return httpx2.Response(200, json=self.offers)
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
                        },
                        "game:readOffers": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/offers"
                        },
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


def test_a_player_is_unlisted_with_the_documented_body():
    handler = FakeApi(add_response={"status": "OK"})

    result = _run(handler, lambda s, c: unlist_from_market(s, c, 3354))

    request = handler.writes[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/exchangemarket/removeplayer")
    # A third spelling of the same id: plural, and a bare array of ints.
    assert json.loads(request.content) == {"tradableIds": [3354]}
    assert result.ok is True
    assert result.unlisted == [3354]


def test_unlisting_reports_failure_when_the_status_is_not_ok():
    handler = FakeApi(add_response={"status": "ERROR"})

    result = _run(handler, lambda s, c: unlist_from_market(s, c, 3354))

    assert result.ok is False


def test_unlisting_is_not_retried_after_a_401():
    handler = FakeApi(add_response={"status": "OK"}, unauthorized_first=True)

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: unlist_from_market(s, c, 3354))

    assert len(handler.writes) == 1


def test_the_asking_price_is_set_with_the_documented_body():
    handler = FakeApi(add_response=True)

    result = _run(handler, lambda s, c: set_asking_price(s, c, 3354, 370_001))

    request = handler.writes[0]
    # A PUT, where the other market actions are POSTs.
    assert request.method == "PUT"
    assert request.url.path.endswith("/exchangemarket/recommendedprice")
    # `playerId` here, and a different word for the amount.
    assert json.loads(request.content) == {"playerId": 3354, "newPrice": 370_001}
    assert result.ok is True
    assert result.player_id == 3354
    assert result.price == 370_001


def test_a_bare_true_is_the_whole_response():
    # Every other action answers with an object. This one answers with a boolean.
    handler = FakeApi(add_response=True)

    result = _run(handler, lambda s, c: set_asking_price(s, c, 3354, 370_001))

    assert result.ok is True


def test_anything_other_than_true_is_a_failure():
    handler = FakeApi(add_response=False)

    result = _run(handler, lambda s, c: set_asking_price(s, c, 3354, 370_001))

    assert result.ok is False


def test_setting_a_price_is_not_retried_after_a_401():
    handler = FakeApi(add_response=True, unauthorized_first=True)

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: set_asking_price(s, c, 3354, 370_001))

    assert len(handler.writes) == 1


def test_a_price_of_zero_is_refused_before_the_put():
    handler = FakeApi(add_response=True)

    with pytest.raises(ValueError):
        _run(handler, lambda s, c: set_asking_price(s, c, 3354, 0))

    assert handler.writes == []


def _offers_payload(*, offerer_id, offer_id=9000003):
    """One open offer, made by `offerer_id`, for a player owned by the other party."""
    return {
        "credit": 1_000_000,
        "items": [
            {
                "id": offer_id,
                "type": "SALE",
                "tradable": {
                    "id": 3871,
                    "name": "Defensa Objetivo",
                    "club": {"id": 5, "name": "Mock FC"},
                    "position": "defender",
                    "trend": 0,
                    "quotedPrice": 810_000,
                    "recommendedPrice": 810_000,
                    "status": "ACTIVE",
                    "statusInfo": "",
                    "points": 0,
                    "onWatchlist": "false",
                },
                "user": {"id": offerer_id, "name": "Somebody"},
                "tradingPartner": {"id": 30000001, "name": "Rival Uno"},
                "price": 810_000,
                "datecreated": "2026-08-10T04:24:03+02:00",
                "datechanged": "2026-08-10T04:24:03+02:00",
                "state": "PENDING",
                "exchange": False,
            }
        ],
        "hasMore": False,
    }


def test_a_bid_is_withdrawn_with_an_empty_body():
    handler = FakeApi(
        add_response={"status": "OK"}, offers=_offers_payload(offerer_id=int(USER_ID))
    )

    result = _run(handler, lambda s, c: withdraw_bid(s, c, 9000003))

    request = handler.writes[0]
    assert request.method == "PUT"
    assert request.url.path.endswith("/offers/9000003")
    assert json.loads(request.content) == {}
    assert result.ok is True
    # The result names what was withdrawn, taken from the offer that was looked up.
    assert result.player == "Defensa Objetivo"
    assert result.price == 810_000


def test_withdrawing_an_incoming_offer_is_refused_before_any_request():
    # `game:offer:withdraw` and `game:offer:decline` share a path, so the same request on
    # somebody else's offer would decline it. Comunio cannot tell them apart for us.
    handler = FakeApi(add_response={"status": "OK"}, offers=_offers_payload(offerer_id=1))

    with pytest.raises(ValueError) as excinfo:
        _run(handler, lambda s, c: withdraw_bid(s, c, 9000003))

    assert "not one of their bids" in str(excinfo.value)
    assert handler.writes == []


def test_withdrawing_an_unknown_offer_is_refused_before_any_request():
    handler = FakeApi(
        add_response={"status": "OK"}, offers=_offers_payload(offerer_id=int(USER_ID))
    )

    with pytest.raises(ValueError) as excinfo:
        _run(handler, lambda s, c: withdraw_bid(s, c, 12345))

    assert "No open offer" in str(excinfo.value)
    assert handler.writes == []


def _market_payload(*, player_id=3871, owner_id=1, owner_name="Computer"):
    return {
        "items": [
            {
                "date": "2026-08-10T04:15:06+0200",
                "remaining": 14,
                "watched": False,
                "_embedded": {
                    "player": {
                        "id": player_id,
                        "name": "Defensa Objetivo",
                        "club": {"id": 5, "name": "Mock FC"},
                        "position": "defender",
                        "trend": 1,
                        "quotedPrice": 810_000,
                        "recommendedPrice": 810_000,
                        "status": "ACTIVE",
                        "statusInfo": "",
                        "points": "-",
                        "purchasePrice": 0,
                        "watched": False,
                    },
                    "owner": {"id": owner_id, "name": owner_name, "communityId": 1},
                },
            }
        ],
        "nextTransfersDateTime": "2026-08-11T03:00:00+02:00",
        "dailyTransfersProcessed": True,
    }


BID_OK = {
    "status": "OK",
    "response": [
        {
            "offerid": 1314490087,
            "tradableid": 3871,
            "price": 810_000,
            "type": "NEW",
            "status": "OK",
            "message": "",
            "processImmediately": False,
        }
    ],
    "opponentIds": "",
}


def _bidding_api(**kwargs):
    return FakeApi(
        add_response=kwargs.pop("add_response", BID_OK),
        market=kwargs.pop("market", _market_payload()),
        offers=kwargs.pop("offers", {"credit": 29_475_000, "items": []}),
        **kwargs,
    )


def test_a_bid_is_placed_with_the_documented_body():
    handler = _bidding_api()

    result = _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    request = handler.writes[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/offers")
    # `tradableid`, all lowercase, unlike every other endpoint.
    assert json.loads(request.content) == {
        "offers": [{"price": 810_000, "tradableid": 3871, "type": "NEW"}]
    }
    assert result.ok is True
    # The offer id is the only handle for changing or withdrawing the bid later.
    assert result.offer_id == 1314490087
    assert result.player == "Defensa Objetivo"
    assert result.applied_immediately is False
    assert result.credit_after == 29_475_000 - 810_000


def test_a_rejected_bid_is_read_from_the_per_item_status():
    # The outer status says OK while the bid itself was refused.
    rejected = {
        "status": "OK",
        "response": [
            {
                "offerid": None,
                "tradableid": 3871,
                "price": 810_000,
                "type": "NEW",
                "status": "ERROR",
                "message": "Credit exceeded",
                "processImmediately": False,
            }
        ],
    }
    handler = _bidding_api(add_response=rejected)

    result = _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    assert result.ok is False
    assert result.message == "Credit exceeded"
    # Nothing was committed, so spending power is unchanged.
    assert result.credit_after == 29_475_000


def test_a_bid_beyond_credit_is_refused_before_anything_is_sent():
    # Credit, not budget: the league's credit factor makes them different numbers.
    handler = _bidding_api(offers={"credit": 500_000, "items": []})

    with pytest.raises(ValueError) as excinfo:
        _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    assert "exceeds the available credit" in str(excinfo.value)
    assert handler.writes == []


def test_bidding_for_a_player_who_is_not_on_the_market_is_refused():
    handler = _bidding_api(market={"items": [], "dailyTransfersProcessed": True})

    with pytest.raises(ValueError) as excinfo:
        _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    assert "not on the market" in str(excinfo.value)
    assert handler.writes == []


def test_bidding_on_your_own_listing_is_refused():
    handler = _bidding_api(
        market=_market_payload(owner_id=int(USER_ID), owner_name="MOCK MANAGER")
    )

    with pytest.raises(ValueError) as excinfo:
        _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    assert "own listing" in str(excinfo.value)
    assert handler.writes == []


def test_a_bid_is_not_retried_after_a_401():
    handler = _bidding_api(unauthorized_first=True)

    with pytest.raises(httpx2.HTTPStatusError):
        _run(handler, lambda s, c: place_bid(s, c, 3871, 810_000))

    assert len(handler.writes) == 1
