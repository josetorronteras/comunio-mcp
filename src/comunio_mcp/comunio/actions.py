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
from comunio_mcp.comunio.models import ListingResult, UnlistResult
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
