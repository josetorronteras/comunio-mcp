"""The transfer market.

The market lives at `game:exchangemarket`, not at `game:tradables` — that one is a
different collection and comes back empty here.

Every listing is HAL with `_embedded`, holding the player and the seller. Two things about
the seller matter enough to be surfaced as their own flags: **user id 1 is Comunio itself**
rather than a rival, and some listings are the signed-in manager's own players, which are
not buyable.
"""

from collections import Counter
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import Market, MarketListing, MarketSummary
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.statuses import meaning

MARKET_LINK = "game:exchangemarket"

#: Comunio lists players itself under a reserved user id. Buying from it is not a
#: negotiation with anybody.
COMPUTER_USER_ID = 1

ACTIVE = "ACTIVE"


async def fetch_market(session: Session, client: ComunioClient) -> Market:
    url = await session.link(MARKET_LINK)
    payload = await client.get(url)
    me = (await session.info()).user_id
    return parse_market(payload, me)


def parse_market(payload: Any, me: str) -> Market:
    listings = [
        _parse_listing(item, me=me) for item in (payload.get("items") or [])
    ]
    return Market(
        closes_at=payload.get("nextTransfersDateTime"),
        daily_transfers_processed=payload.get("dailyTransfersProcessed", False),
        summary=_summarise(listings),
        listings=listings,
    )


def _parse_listing(item: dict, *, me: str) -> MarketListing:
    embedded = item.get("_embedded") or {}
    player = embedded.get("player") or {}
    owner = embedded.get("owner") or {}
    owner_id = owner.get("id")

    return MarketListing.model_validate(
        {
            **player,
            "status_meaning": meaning(player.get("status")),
            "seller": owner.get("name", ""),
            "seller_id": owner_id,
            "from_computer": owner_id == COMPUTER_USER_ID,
            "is_mine": str(owner_id) == str(me),
            "listed_at": item.get("date"),
            "remaining": item.get("remaining", 0),
            "watched": item.get("watched", False),
        }
    )


def _summarise(listings: list[MarketListing]) -> MarketSummary:
    return MarketSummary(
        total=len(listings),
        from_computer=sum(1 for listing in listings if listing.from_computer),
        from_managers=sum(1 for listing in listings if not listing.from_computer),
        mine=sum(1 for listing in listings if listing.is_mine),
        unavailable=sum(1 for listing in listings if listing.status != ACTIVE),
        by_position=dict(Counter(listing.position for listing in listings)),
    )
