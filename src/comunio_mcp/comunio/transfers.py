"""Completed transfers, extracted from the league news feed.

There is no transfers endpoint. Transfers arrive as one entry per day in `game:news`,
alongside promotional HTML, welcome messages and administration notices. Only the
`TRANSACTION_TRANSFER` entries are of any use here, so the rest is discarded rather than
handed to a model: a single marketing entry in that feed is longer than every transfer in
it put together.

What makes these worth reading is that they are **settled prices** — what a player actually
went for, rather than what the market quotes.
"""

import logging
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.market import COMPUTER_USER_ID
from comunio_mcp.comunio.models import Transfer, Transfers, TransfersSummary
from comunio_mcp.comunio.session import Session

logger = logging.getLogger(__name__)

NEWS_LINK = "game:news"

TRANSFER_TYPE = "TRANSACTION_TRANSFER"

#: `originaltypes=true` is load-bearing: without it Comunio collapses the entry types to
#: coarse ones (`TRANSACTION` instead of `TRANSACTION_TRANSFER`) and they cannot be told
#: apart. `group=true` only nests the entries under dates, which is more work to undo. The
#: web app also sends `type=HIDDEN_NEWS`, which was measured to change nothing.
BASE_PARAMS = "originaltypes=true"

#: The server caps a page at 20 however large a limit is requested.
PAGE_SIZE = 20

#: Stops a request for a big limit from walking the whole history of the league.
MAX_PAGES = 10


async def fetch_transfers(
    session: Session, client: ComunioClient, limit: int = 50
) -> Transfers:
    url = await session.link(NEWS_LINK)
    me = (await session.info()).user_id

    transfers: list[Transfer] = []
    has_more = False

    for page in range(MAX_PAGES):
        payload = await client.get(
            f"{url}?{BASE_PARAMS}&start={page * PAGE_SIZE}&limit={PAGE_SIZE}"
        )
        news = payload.get("newsList") or {}
        entries = news.get("entries") or []
        has_more = bool(news.get("hasMore"))

        transfers.extend(parse_transfer_entries(entries, me=me))

        if len(transfers) >= limit or not entries or not has_more:
            break
    else:
        logger.info("Stopped after %d pages of news", MAX_PAGES)

    if len(transfers) > limit:
        transfers, has_more = transfers[:limit], True

    return Transfers(summary=_summarise(transfers, me=me), has_more=has_more, transfers=transfers)


def parse_transfer_entries(entries: list[dict], *, me: str) -> list[Transfer]:
    return [
        transfer
        for entry in entries
        if entry.get("type") == TRANSFER_TYPE
        for transfer in _parse_entry(entry, me=me)
    ]


def _parse_entry(entry: dict, *, me: str) -> list[Transfer]:
    """One entry is a day's worth of transfers, bucketed by kind."""
    date = entry.get("date")
    message = entry.get("message")
    if not isinstance(message, dict):
        return []

    transfers = []
    # Iterate whatever buckets are present rather than naming them. Only FROM_COMPUTER and
    # TO_COMPUTER have been observed, but manager-to-manager deals presumably arrive under
    # a third key, and dropping them silently would be worse than not knowing the name.
    for kind, moves in message.items():
        if not isinstance(moves, list):
            continue
        transfers.extend(_parse_move(move, kind=kind, date=date, me=me) for move in moves)

    return transfers


def _parse_move(move: dict, *, kind: str, date: Any, me: str) -> Transfer:
    player = move.get("tradable") or {}
    seller = move.get("from") or {}
    buyer = move.get("to") or {}

    return Transfer(
        player_id=player.get("id"),
        player=player.get("name", ""),
        price=move.get("price", 0),
        from_manager=(seller.get("name") or "").strip(),
        from_id=seller.get("id"),
        to_manager=(buyer.get("name") or "").strip(),
        to_id=buyer.get("id"),
        kind=kind,
        from_computer=seller.get("id") == COMPUTER_USER_ID,
        to_computer=buyer.get("id") == COMPUTER_USER_ID,
        involves_me=str(seller.get("id")) == str(me) or str(buyer.get("id")) == str(me),
        date=date,
        immediate_at=move.get("immediateTransferTime"),
    )


def _summarise(transfers: list[Transfer], *, me: str) -> TransfersSummary:
    return TransfersSummary(
        total=len(transfers),
        bought_from_computer=sum(1 for t in transfers if t.from_computer),
        sold_to_computer=sum(1 for t in transfers if t.to_computer),
        between_managers=sum(1 for t in transfers if not t.from_computer and not t.to_computer),
        mine=sum(1 for t in transfers if t.involves_me),
        total_value=sum(t.price for t in transfers),
    )
