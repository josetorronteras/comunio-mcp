"""The watchlist: players the manager is keeping an eye on.

Three endpoints on one path. Reading is a plain GET; adding is a `POST` with an **empty
body**; removing is a `DELETE` that nonetheless **carries a JSON body**, which is unusual
enough to be worth stating rather than discovering.

Entries are flat, and spell the price `quotedprice` — the squad's spelling, not the
market's `quotedPrice`. The useful part is `owner`, which is **null when nobody holds the
player**: a watched player with no owner can only ever arrive through the market, while
one held by a rival needs a deal or a buyout clause.
"""

from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import WatchedPlayer, Watchlist, WatchResult
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.statuses import meaning

WATCHLIST_LINK = "game:watchlist"

OK = "OK"


async def fetch_watchlist(session: Session, client: ComunioClient) -> Watchlist:
    payload = await client.get(await session.link(WATCHLIST_LINK))
    return parse_watchlist(payload)


def parse_watchlist(payload: Any) -> Watchlist:
    entries = (payload or {}).get("tradables") or []
    players = [_parse_entry(entry) for entry in entries if isinstance(entry, dict)]
    return Watchlist(
        total=len(players),
        unowned=sum(1 for player in players if player.unowned),
        players=players,
    )


def _parse_entry(entry: dict) -> WatchedPlayer:
    club = entry.get("club") or {}
    owner = entry.get("owner")

    return WatchedPlayer(
        id=entry.get("id"),
        name=entry.get("name", ""),
        club=club.get("name", ""),
        position=entry.get("position", ""),
        status=entry.get("status", ""),
        status_meaning=meaning(entry.get("status")),
        status_info=entry.get("statusInfo"),
        disabled=bool(entry.get("disabled")),
        quoted_price=entry.get("quotedprice", 0),
        trend=entry.get("trend"),
        points=entry.get("points"),
        last_points=entry.get("lastPoints"),
        owner=(owner or {}).get("name") if isinstance(owner, dict) else None,
        owner_id=(owner or {}).get("id") if isinstance(owner, dict) else None,
        unowned=owner is None,
    )


async def watch_player(session: Session, client: ComunioClient, player_id: int) -> WatchResult:
    """Start watching a player. The request carries no body at all."""
    url = f"{await session.link(WATCHLIST_LINK)}/players/{player_id}"
    payload = await client.post(url, json={})

    return WatchResult(ok=_accepted(payload), player_id=player_id, watching=True)


async def unwatch_player(session: Session, client: ComunioClient, player_id: int) -> WatchResult:
    """Stop watching a player. A DELETE that Comunio expects to carry a body."""
    url = f"{await session.link(WATCHLIST_LINK)}/players/{player_id}"
    payload = await client.delete(url, json={})

    return WatchResult(ok=_accepted(payload), player_id=player_id, watching=False)


def _accepted(payload: Any) -> bool:
    if isinstance(payload, dict):
        return payload.get("status") == OK
    # Adding answers with fifteen bytes and removing with a status object; a bare boolean
    # would not be out of character for this API.
    return payload is True
