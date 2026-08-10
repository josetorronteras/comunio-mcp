"""Actions that change something in Comunio.

Everything here mutates. Two rules apply to all of it:

* **No retries.** `ComunioClient.post` and `put` take a failure as a failure. A write that
  reached Comunio and lost its response would be applied twice by a retry.
* **Never trust the outer `status`.** These endpoints are batches and report per item.
  An outer `OK` with a rejected item inside is possible, and reporting success from the
  outer field is how a tool claims to have done something it did not do.
"""

from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.market import fetch_market
from comunio_mcp.comunio.models import (
    AcceptResult,
    AskingPriceResult,
    BidResult,
    ListingResult,
    UnlistResult,
    WithdrawResult,
)
from comunio_mcp.comunio.offers import INCOMING, OFFERS_LINK, OUTGOING, fetch_offers
from comunio_mcp.comunio.session import Session

MARKET_LINK = "game:exchangemarket"

OK = "OK"


async def list_on_market(
    session: Session, client: ComunioClient, player_id: int, price: int
) -> ListingResult:
    """Put one of the manager's own players up for sale at `price`."""
    if price <= 0:
        raise ValueError("An asking price must be greater than zero")

    url = f"{await session.link(MARKET_LINK)}/addplayer"
    payload = await client.post(url, json={"items": [{"tradableId": player_id, "price": price}]})

    return parse_listing_result(payload, requested=[player_id])


def parse_listing_result(payload: Any, *, requested: list[int]) -> ListingResult:
    # `notPlaced` is the only statement about failure; the outer `status` says nothing
    # about individual players.
    rejected = [int(entry) for entry in _ids(payload.get("notPlaced"))]
    placed = [player_id for player_id in requested if player_id not in rejected]

    return ListingResult(
        placed=placed, rejected=rejected, remaining=payload.get("remaining")
    )


def _ids(not_placed: Any) -> list:
    """`notPlaced` has only ever been seen empty, so accept the shapes it might take."""
    if not not_placed:
        return []
    if isinstance(not_placed, dict):
        return list(not_placed)
    return [
        entry.get("tradableId", entry.get("tradableid")) if isinstance(entry, dict) else entry
        for entry in not_placed
    ]


async def unlist_from_market(
    session: Session, client: ComunioClient, player_id: int
) -> UnlistResult:
    """Take one of the manager's own players back off the market."""
    url = f"{await session.link(MARKET_LINK)}/removeplayer"
    # A third spelling of the same id: plural, and a bare array of ints.
    payload = await client.post(url, json={"tradableIds": [player_id]})

    return parse_unlist_result(payload, requested=[player_id])


def parse_unlist_result(payload: Any, *, requested: list[int]) -> UnlistResult:
    return UnlistResult(ok=payload.get("status") == OK, unlisted=requested)


async def set_asking_price(
    session: Session, client: ComunioClient, player_id: int, price: int
) -> AskingPriceResult:
    """Change the asking price of a player the manager already has on the market.

    Named for what it does. Comunio calls the route `recommendedprice`, but it does not
    touch Comunio's own recommendation — it sets the manager's own price.
    """
    if price <= 0:
        raise ValueError("An asking price must be greater than zero")

    url = f"{await session.link(MARKET_LINK)}/recommendedprice"
    # A second spelling again: `playerId`, and a different word for the amount.
    payload = await client.put(url, json={"playerId": player_id, "newPrice": price})

    return parse_asking_price_result(payload, player_id=player_id, price=price)


def parse_asking_price_result(payload: Any, *, player_id: int, price: int) -> AskingPriceResult:
    # The response is a bare boolean rather than an object, unlike every other action.
    return AskingPriceResult(ok=payload is True, player_id=player_id, price=price)


async def withdraw_bid(session: Session, client: ComunioClient, offer_id: int) -> WithdrawResult:
    """Withdraw one of the manager's own pending bids.

    Guarded on purpose. `game:offer:withdraw` and `game:offer:decline` point at the *same*
    path, so the same request on somebody else's offer would decline it instead of
    withdrawing the manager's own. Comunio gives no way to tell which is which from the
    id, so the offer is looked up first and anything that is not an outgoing bid is
    refused before a request is sent.
    """
    offers = await fetch_offers(session, client)
    match = next((offer for offer in offers.offers if offer.offer_id == offer_id), None)

    if match is None:
        raise ValueError(
            f"No open offer with id {offer_id}. Check get_offers for the current ones."
        )
    if match.direction != OUTGOING:
        raise ValueError(
            f"Offer {offer_id} is an offer for the manager's own player, not one of their "
            "bids. Withdrawing is only for bids the manager made."
        )

    url = f"{await session.link(OFFERS_LINK)}/{offer_id}"
    payload = await client.put(url, json={})

    return WithdrawResult(
        ok=payload.get("status") == OK,
        offer_id=offer_id,
        player=match.player.name,
        price=match.price,
    )


BID_NEW = "NEW"
BID_CHANGE = "CHANGE"
OFFER_ACCEPT = "ACCEPT"


async def place_bid(
    session: Session, client: ComunioClient, player_id: int, price: int
) -> BidResult:
    """Bid for a player on the market.

    Checked before anything is sent, because this commits money:

    * the player is actually on the market, and is not one of the manager's own;
    * the bid fits within **credit**, which is what can really be spent — not the budget
      `get_account` reports, which the league's credit factor lets it exceed.
    """
    if price <= 0:
        raise ValueError("A bid must be greater than zero")

    market = await fetch_market(session, client)
    listing = next((item for item in market.listings if item.player_id == player_id), None)
    if listing is None:
        raise ValueError(
            f"Player {player_id} is not on the market. Check get_market for what is."
        )
    if listing.is_mine:
        raise ValueError(
            f"{listing.name} is one of the manager's own listings, so bidding on it is not a move"
        )

    offers = await fetch_offers(session, client)
    if price > offers.credit:
        raise ValueError(
            f"A bid of {price:,} exceeds the available credit of {offers.credit:,}"
        )

    url = await session.link(OFFERS_LINK)
    payload = await client.post(
        url,
        # Yet another spelling: `tradableid`, all lowercase.
        json={"offers": [{"price": price, "tradableid": player_id, "type": BID_NEW}]},
    )

    return parse_bid_result(
        payload,
        player_id=player_id,
        price=price,
        player=listing.name,
        credit=offers.credit,
    )


def parse_bid_result(
    payload: Any, *, player_id: int, price: int, player: str | None, credit: int | None
) -> BidResult:
    # The outer `status` only says the request was processed. Whether *this* bid was
    # accepted is the per-item status, and an outer OK with a rejected item inside is
    # possible.
    items = payload.get("response") or []
    item = items[0] if items else {}
    ok = item.get("status") == OK

    return BidResult(
        ok=ok,
        message=item.get("message"),
        offer_id=item.get("offerid"),
        player_id=player_id,
        player=player,
        price=price,
        applied_immediately=bool(item.get("processImmediately")),
        credit_after=(credit - price) if ok and credit is not None else credit,
    )


async def change_bid(
    session: Session, client: ComunioClient, offer_id: int, price: int
) -> BidResult:
    """Change the amount of a bid the manager has already placed.

    The player is taken from the offer being changed rather than from an argument, so a
    change cannot quietly end up pointing at a different player.

    Guarded like `withdraw_bid`: an id that belongs to an offer *for* one of the manager's
    players is not theirs to change.
    """
    if price <= 0:
        raise ValueError("A bid must be greater than zero")

    offers = await fetch_offers(session, client)
    match = next((offer for offer in offers.offers if offer.offer_id == offer_id), None)

    if match is None:
        raise ValueError(
            f"No open offer with id {offer_id}. Check get_offers for the current ones."
        )
    if match.direction != OUTGOING:
        raise ValueError(
            f"Offer {offer_id} is an offer for the manager's own player, not one of their "
            "bids. Only the manager's own bids can be changed."
        )
    if price > offers.credit:
        raise ValueError(
            f"A bid of {price:,} exceeds the available credit of {offers.credit:,}"
        )

    url = await session.link(OFFERS_LINK)
    payload = await client.post(
        url,
        json={
            "offers": [
                {
                    "price": price,
                    "type": BID_CHANGE,
                    "offerid": offer_id,
                    "tradableid": match.player.id,
                }
            ]
        },
    )

    return parse_bid_result(
        payload,
        player_id=match.player.id,
        price=price,
        player=match.player.name,
        credit=offers.credit,
    )


async def accept_offer(session: Session, client: ComunioClient, offer_id: int) -> AcceptResult:
    """Accept an offer for one of the manager's players.

    **The only irreversible action here.** `processImmediately` comes back true: the player
    leaves the squad at once, with no transfer round to wait through and nothing to undo it
    with.

    The player and the price are taken from the offer, never from arguments, so what is
    accepted is exactly what was offered.
    """
    offers = await fetch_offers(session, client)
    match = next((offer for offer in offers.offers if offer.offer_id == offer_id), None)

    if match is None:
        raise ValueError(
            f"No open offer with id {offer_id}. Check get_offers for the current ones."
        )
    if match.direction != INCOMING:
        raise ValueError(
            f"Offer {offer_id} is a bid the manager made, not an offer for one of their "
            "players. There is nothing to accept."
        )

    url = await session.link(OFFERS_LINK)
    payload = await client.post(
        url,
        json={
            "offers": [
                {
                    "offerid": offer_id,
                    "tradableid": match.player.id,
                    "price": match.price,
                    "type": OFFER_ACCEPT,
                }
            ]
        },
    )

    items = payload.get("response") or []
    item = items[0] if items else {}

    return AcceptResult(
        ok=item.get("status") == OK,
        message=item.get("message"),
        offer_id=offer_id,
        player_id=match.player.id,
        player=match.player.name,
        price=match.price,
        premium=match.premium,
        premium_pct=match.premium_pct,
        buyer=match.offered_by,
        applied_immediately=bool(item.get("processImmediately")),
    )
