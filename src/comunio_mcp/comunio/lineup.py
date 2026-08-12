"""Setting the lineup.

The endpoint takes numbered slots, `"1"` to `"11"`, and it never says what a number means.
The mapping was worked out by cross-referencing two real lineups against the squad: in a
442 the keeper sat in slot 11 and a striker in slot 1; in a 343 the same. So slots fill
**from the strikers backwards**, and 11 is always the keeper:

```
343 → 1,2,3 strikers · 4,5,6,7 midfielders · 8,9,10 defenders · 11 keeper
442 → 1,2   strikers · 3,4,5,6 midfielders · 7,8,9,10 defenders · 11 keeper
```

That arithmetic belongs here rather than in a prompt, so the tool takes players by
position and works the numbers out.

A partial lineup is allowed — Comunio's own interface warns that each empty slot costs
four points rather than refusing it — so slots may be left empty, and the result says how
many and what that is worth.
"""

from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import LineupResult, LineupSlot
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.squad import fetch_squad
from comunio_mcp.comunio.statuses import AVAILABLE

LINEUP_LINK = "game:lineup"

KEEPER, DEFENDER, MIDFIELDER, STRIKER = "keeper", "defender", "midfielder", "striker"

KEEPER_SLOT = 11

#: The five formations Comunio accepts, as defenders–midfielders–strikers.
TACTICS: dict[str, tuple[int, int, int]] = {
    "442": (4, 4, 2),
    "343": (3, 4, 3),
    "352": (3, 5, 2),
    "433": (4, 3, 3),
    "451": (4, 5, 1),
}

#: What Comunio's own interface says an unfilled slot costs. Taken from its wording, not
#: measured.
POINTS_PER_EMPTY_SLOT = 4

SUBSTITUTE_POSITIONS = (STRIKER, MIDFIELDER, DEFENDER, KEEPER)


class LineupError(ValueError):
    """The lineup as asked for is not one Comunio would accept."""


def slot_plan(tactic: str) -> list[tuple[int, str]]:
    """Which slot number holds which position, for a formation."""
    defenders, midfielders, strikers = TACTICS[tactic]

    plan = []
    slot = 1
    for position, count in ((STRIKER, strikers), (MIDFIELDER, midfielders), (DEFENDER, defenders)):
        for _ in range(count):
            plan.append((slot, position))
            slot += 1
    plan.append((KEEPER_SLOT, KEEPER))
    return plan


async def set_lineup(
    session: Session,
    client: ComunioClient,
    *,
    tactic: str,
    keeper: int | None = None,
    defenders: list[int] | None = None,
    midfielders: list[int] | None = None,
    strikers: list[int] | None = None,
) -> LineupResult:
    if tactic not in TACTICS:
        raise LineupError(
            f"{tactic!r} is not a formation Comunio accepts. Valid: "
            + ", ".join(sorted(TACTICS))
        )

    chosen = {
        KEEPER: [keeper] if keeper else [],
        DEFENDER: list(defenders or []),
        MIDFIELDER: list(midfielders or []),
        STRIKER: list(strikers or []),
    }

    squad = await fetch_squad(session, client)
    by_id = {player.id: player for player in squad.players}
    _validate(chosen, tactic=tactic, by_id=by_id)

    plan = slot_plan(tactic)
    remaining = {position: list(ids) for position, ids in chosen.items()}
    slots: dict[str, str] = {}
    fielded: list[LineupSlot] = []

    for slot, position in plan:
        queue = remaining[position]
        player_id = queue.pop(0) if queue else None
        slots[str(slot)] = str(player_id) if player_id else ""
        if player_id:
            fielded.append(
                LineupSlot(
                    slot=slot,
                    position=position,
                    player_id=player_id,
                    player=by_id[player_id].name,
                    status=by_id[player_id].status,
                )
            )

    info = (await session.info())
    payload = await client.put(
        await session.link(LINEUP_LINK),
        json={
            "userId": int(info.user_id),
            "tactic": tactic,
            "lineup": slots,
            "substitutes": {position: "" for position in SUBSTITUTE_POSITIONS},
            "type": "default",
        },
    )

    empty = sum(1 for value in slots.values() if not value)
    return LineupResult(
        ok=payload.get("status") == "OK",
        tactic=tactic,
        fielded=fielded,
        empty_slots=empty,
        penalty_points=empty * POINTS_PER_EMPTY_SLOT,
        unavailable=[slot.player for slot in fielded if slot.status != AVAILABLE],
        out_of_position=[
            f"{slot.player} is a {by_id[slot.player_id].position} played at {slot.position}"
            for slot in fielded
            if by_id[slot.player_id].position != slot.position
        ],
    )


def _validate(chosen: dict[str, list[int]], *, tactic: str, by_id: dict[int, Any]) -> None:
    defenders, midfielders, strikers = TACTICS[tactic]
    allowed = {KEEPER: 1, DEFENDER: defenders, MIDFIELDER: midfielders, STRIKER: strikers}

    everyone = [player_id for ids in chosen.values() for player_id in ids]

    duplicates = {player_id for player_id in everyone if everyone.count(player_id) > 1}
    if duplicates:
        raise LineupError(f"The same player cannot fill two slots: {sorted(duplicates)}")

    missing = [player_id for player_id in everyone if player_id not in by_id]
    if missing:
        raise LineupError(f"Not in the squad: {sorted(missing)}")

    for position, ids in chosen.items():
        # Not a rule of the game — a limit of the request. `slot_plan` has exactly this
        # many slots for the position, so anything beyond them would be dropped in
        # silence, and the caller would be told a lineup was set that never was.
        if len(ids) > allowed[position]:
            raise LineupError(
                f"A {tactic} has room for {allowed[position]} at {position}, not {len(ids)}"
            )
