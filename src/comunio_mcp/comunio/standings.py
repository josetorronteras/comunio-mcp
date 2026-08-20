"""The league table.

Two things set this endpoint apart from the others:

* It **requires query parameters**. Without `period` and `wpe` the response is not JSON at
  all, so a bare GET on the link fails in a confusing way.
* It is HAL with `_embedded`, a shape the index does not use: the manager and their team
  live nested inside each row rather than alongside the figures.
"""

from typing import Any, Literal

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import Standings, StandingsRow
from comunio_mcp.comunio.session import Session

STANDINGS_LINK = "game:standings"

#: The two periods the web app is known to request. `total` is the season table;
#: `live` is the same table recomputed for the matchday in progress, and it is the only
#: one that fills `livePoints`, `playersPossiblyScoredAmount` and `negativeBudget` —
#: under `total` those come back null, 0 and false even when a manager is in the red.
Period = Literal["total", "live"]

#: `wpe` is undocumented; the web app always sends it and the endpoint needs it.
WPE = "true"


async def fetch_standings(
    session: Session,
    client: ComunioClient,
    period: Period = "total",
) -> Standings:
    url = await session.link(STANDINGS_LINK)
    payload = await client.get(url, params={"period": period, "wpe": WPE})
    me = (await session.info()).user_id
    return parse_standings(payload, me)


def parse_standings(payload: Any, me: str) -> Standings:
    rows = [
        _parse_row(item, rank=rank, me=me)
        for rank, item in enumerate(payload.get("items") or [], start=1)
    ]
    return Standings(period=payload.get("id") or "total", rows=rows)


def _parse_row(item: dict, *, rank: int, me: str) -> StandingsRow:
    embedded = item.get("_embedded") or {}
    user = embedded.get("user") or {}
    team = embedded.get("teamInfo") or {}

    manager_id = user.get("id")

    return StandingsRow(
        # Before the season starts every `position` in the payload is 0, so the table's
        # own ranking field is useless. Rank comes from the order Comunio sends.
        rank=rank,
        is_me=str(manager_id) == str(me),
        manager_id=manager_id,
        # Comunio pads some names with a trailing space, as it does in offers
        # and transfers. Without stripping, the same manager fails to match
        # across tools.
        manager=(user.get("name") or "").strip(),
        total_points=item.get("totalPoints", 0),
        last_points=item.get("lastPoints"),
        live_points=item.get("livePoints"),
        perennial_points=item.get("totalPerennialPoints", 0),
        players_possibly_scoring=item.get("playersPossiblyScoredAmount", 0),
        team_value=team.get("teamValue", 0),
        negative_budget=user.get("negativeBudget", False),
    )
