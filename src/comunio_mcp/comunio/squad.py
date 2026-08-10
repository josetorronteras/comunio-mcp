"""The squad endpoint: the manager's players.

The richest endpoint in the API and the one the lineup and market work builds on. It
carries availability (`status`, `statusInfo`), scoring, prices, who is currently lined up,
and each player's next fixture — which is where a lineup deadline will come from.
"""

from collections import Counter
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import Squad, SquadPlayer, SquadSummary
from comunio_mcp.comunio.session import Session

SQUAD_LINK = "game:squad"

ACTIVE = "ACTIVE"


async def fetch_squad(
    session: Session, client: ComunioClient, manager_id: int | None = None
) -> Squad:
    """Fetch a squad. Defaults to the signed-in manager's own.

    The endpoint takes a user id, so a rival's squad is the same call with a different
    one. There is nothing to hide behind: prices, injuries and squad depth are all
    visible.
    """
    me = (await session.info()).user_id
    url = await session.link(SQUAD_LINK, userId=str(manager_id) if manager_id else me)
    return parse_squad(await client.get(url), me=me)


def parse_squad(payload: Any, me: str | None = None) -> Squad:
    items = payload["items"]
    players = [_parse_player(item) for item in items]
    owner = (items[0].get("owner") or {}) if items else {}
    owner_id = owner.get("id")

    return Squad(
        owner=owner.get("name"),
        owner_id=owner_id,
        is_mine=me is not None and str(owner_id) == str(me),
        tactic=payload.get("tactic", ""),
        summary=_summarise(players),
        players=players,
    )


def _parse_player(item: dict) -> SquadPlayer:
    # Flatten the two nested objects worth keeping and let the allowlist drop the rest,
    # which is mostly `_links` for logos, photos and watchlist actions.
    next_match = _parse_next_match(item.get("nextMatch"))
    return SquadPlayer.model_validate({**item, "nextMatch": next_match})


def _parse_next_match(match: dict | None) -> dict | None:
    if not match:
        return None
    return {
        "home": match["home"]["name"],
        "away": match["guest"]["name"],
        "kickoff": match["kickoff"],
    }


def _summarise(players: list[SquadPlayer]) -> SquadSummary:
    return SquadSummary(
        total=len(players),
        lined_up=sum(1 for p in players if p.linedup),
        substitutes=sum(1 for p in players if p.substitute),
        unavailable=sum(1 for p in players if p.status != ACTIVE),
        on_market=sum(1 for p in players if p.on_market),
        by_position=dict(Counter(p.position for p in players)),
    )
