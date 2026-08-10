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
from comunio_mcp.comunio.models import (
    AskingPriceResult,
    ListingResult,
    UnlistResult,
    WithdrawResult,
)
from comunio_mcp.comunio.offers import OFFERS_LINK, OUTGOING, fetch_offers
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
