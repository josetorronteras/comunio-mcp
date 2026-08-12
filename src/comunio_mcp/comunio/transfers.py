"""Completed transfers, from the offers history.

`game:readOffersHistory` is the settled half of the same collection `get_offers` reads
while it is still open: every offer that went through, `state: PROCESSED`.

These were previously reconstructed from the league news feed, which has no transfers
endpoint of its own and files them as one digest entry per day. Measured against a real
league, the two carry **exactly the same 31 movements** over the same five days, and the
history does it in one request where the feed needed twelve. The feed still backs
`get_news`; it is no longer the source for transfers.

What makes these worth reading is that they are **settled prices** — what a player actually
went for, rather than what the market quotes. `quoted_price` comes back alongside, so the
two can be compared without a second call.
"""

import logging

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.market import COMPUTER_USER_ID
from comunio_mcp.comunio.models import Transfer, Transfers, TransfersSummary
from comunio_mcp.comunio.session import Session

logger = logging.getLogger(__name__)

HISTORY_LINK = "game:readOffersHistory"

#: One page. Unlike the news feed, this endpoint **honours the limit it is given**:
#: measured at 20, 50, 100 and 200, it returned everything there was and reported
#: `hasMore: false`. So this is a default, not a ceiling.
DEFAULT_LIMIT = 20

#: Stops a request for a huge limit from walking the league's whole history.
MAX_PAGES = 10


async def fetch_transfers(
    session: Session, client: ComunioClient, limit: int = DEFAULT_LIMIT
) -> Transfers:
    url = await session.link(HISTORY_LINK)
    me = (await session.info()).user_id

    transfers: list[Transfer] = []
    has_more = False

    for _ in range(MAX_PAGES):
        remaining = limit - len(transfers)
        payload = await client.get(f"{url}?offset={len(transfers)}&limit={remaining}")
        items = payload.get("items") or []
        has_more = bool(payload.get("hasMore"))

        transfers.extend(parse_transfers(items, me=me))

        if len(transfers) >= limit or not items or not has_more:
            break
    else:
        logger.info("Stopped after %d pages of offer history", MAX_PAGES)

    if len(transfers) > limit:
        transfers, has_more = transfers[:limit], True

    return Transfers(summary=_summarise(transfers, me=me), has_more=has_more, transfers=transfers)


def parse_transfers(items: list[dict], *, me: str) -> list[Transfer]:
    return [_parse(item, me=me) for item in items if isinstance(item, dict)]


def _parse(item: dict, *, me: str) -> Transfer:
    player = item.get("tradable") or {}
    club = player.get("club") or {}

    # Which way the player moved. Nothing in the payload states it, and the field that
    # looks like it does is a trap — see `_direction`.
    seller, buyer = _direction(item)

    return Transfer(
        offer_id=item.get("id"),
        player_id=player.get("id"),
        # Some names arrive padded on both sides, e.g. " Fran González ".
        player=(player.get("name") or "").strip(),
        club=(club.get("name") or "").strip() or None,
        position=player.get("position"),
        status=player.get("status"),
        price=item.get("price", 0),
        quoted_price=player.get("quotedPrice"),
        from_manager=(seller.get("name") or "").strip(),
        from_id=seller.get("id"),
        to_manager=(buyer.get("name") or "").strip(),
        to_id=buyer.get("id"),
        from_computer=seller.get("id") == COMPUTER_USER_ID,
        to_computer=buyer.get("id") == COMPUTER_USER_ID,
        involves_me=str(seller.get("id")) == str(me) or str(buyer.get("id")) == str(me),
        offered_at=item.get("datecreated"),
        settled_at=item.get("datechanged"),
    )


def _direction(item: dict) -> tuple[dict, dict]:
    """Who the player came from and who they went to.

    The payload does not say. `type` looks like the answer and is not: measured across a
    real league's whole history, `SALE` appeared 15 times on a player moving *to* Comunio
    and 13 times on one moving *from* it. Reading direction off it would be wrong for a
    third of the rows.

    What does hold, on 31 of 31 checked against the same deals in the news feed:

    * **`tradable.owner`** is who held the player when the offer was made — the seller.
    * **`user`** is who the offer belongs to — the buyer.

    `tradingPartner` repeats the owner, so it adds nothing.
    """
    return (item.get("tradable") or {}).get("owner") or {}, item.get("user") or {}


def _summarise(transfers: list[Transfer], *, me: str) -> TransfersSummary:
    return TransfersSummary(
        total=len(transfers),
        bought_from_computer=sum(1 for t in transfers if t.from_computer),
        sold_to_computer=sum(1 for t in transfers if t.to_computer),
        between_managers=sum(1 for t in transfers if not t.from_computer and not t.to_computer),
        mine=sum(1 for t in transfers if t.involves_me),
        total_value=sum(t.price for t in transfers),
    )
