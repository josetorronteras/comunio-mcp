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

from dataclasses import dataclass
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import LineupResult, LineupSlot, SquadPlayer
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
        if len(ids) > allowed[position]:
            raise LineupError(
                f"A {tactic} has room for {allowed[position]} at {position}, not {len(ids)}"
            )
        for player_id in ids:
            actual = by_id[player_id].position
            if actual != position:
                raise LineupError(
                    f"{by_id[player_id].name} is a {actual} and cannot be played at {position}"
                )


@dataclass(frozen=True)
class LineupPlan:
    """A deterministic starting eleven, not yet applied to Comunio.

    `payload` is exactly the keyword arguments `set_lineup()` needs, so an execution can
    apply it unchanged — the proposal and what gets sent to Comunio are never allowed to
    differ.
    """

    tactic: str
    fielded: list[tuple[int, str, SquadPlayer]]
    empty_slots: int
    estimated_points: float
    penalty_points: int
    summary: str
    payload: dict[str, Any]


def _rank_key(player: SquadPlayer) -> tuple[bool, float, int]:
    """Available first, then season average, then id to break ties deterministically.

    The id tie-break matters today: a pre-season squad has `average_points == 0`
    throughout, so without it the pick among equal players would be arbitrary rather than
    reproducible.
    """
    return (player.status == AVAILABLE, player.average_points or 0.0, player.id)


def _pick(candidates: list[SquadPlayer], count: int) -> list[SquadPlayer]:
    return sorted(candidates, key=_rank_key, reverse=True)[:count]


def _summarize(
    tactic: str, fielded: list[tuple[int, str, SquadPlayer]], empty: int, penalty: int
) -> str:
    lines = [f"{tactic}:"]
    for _, position, player in sorted(fielded, key=lambda item: item[0]):
        average = player.average_points or 0.0
        flag = "" if player.status == AVAILABLE else f" ({player.status})"
        lines.append(f"  {position}: {player.name}{flag}, avg {average:.1f}")
    if empty:
        lines.append(f"  {empty} slot(s) left empty, -{penalty} points")
    return "\n".join(lines)


def _plan_for_tactic(by_position: dict[str, list[SquadPlayer]], tactic: str) -> LineupPlan:
    defenders, midfielders, strikers = TACTICS[tactic]
    needed = {STRIKER: strikers, MIDFIELDER: midfielders, DEFENDER: defenders, KEEPER: 1}
    chosen = {
        position: _pick(by_position.get(position, []), count)
        for position, count in needed.items()
    }

    plan = slot_plan(tactic)
    remaining = {position: list(players) for position, players in chosen.items()}
    fielded: list[tuple[int, str, SquadPlayer]] = []
    for slot, position in plan:
        queue = remaining[position]
        if queue:
            fielded.append((slot, position, queue.pop(0)))

    empty = len(plan) - len(fielded)
    points = sum(player.average_points or 0.0 for _, _, player in fielded)
    penalty = empty * POINTS_PER_EMPTY_SLOT

    keeper_id: int | None = None
    defender_ids: list[int] = []
    midfielder_ids: list[int] = []
    striker_ids: list[int] = []
    for _, position, player in fielded:
        if position == KEEPER:
            keeper_id = player.id
        elif position == DEFENDER:
            defender_ids.append(player.id)
        elif position == MIDFIELDER:
            midfielder_ids.append(player.id)
        else:
            striker_ids.append(player.id)

    return LineupPlan(
        tactic=tactic,
        fielded=fielded,
        empty_slots=empty,
        estimated_points=points,
        penalty_points=penalty,
        summary=_summarize(tactic, fielded, empty, penalty),
        payload={
            "tactic": tactic,
            "keeper": keeper_id,
            "defenders": defender_ids,
            "midfielders": midfielder_ids,
            "strikers": striker_ids,
        },
    )


def best_lineup(players: list[SquadPlayer], *, tactic: str | None = None) -> LineupPlan:
    """Work out the best starting eleven from a squad, without applying it.

    Ranks each position's candidates by availability first, then season average points,
    and fills the formation's slots from the top. Positions are independent — a player
    cannot fill another position's slot — so taking the top N by rank per position is
    optimal for maximising total points under a fixed slot count, the same reasoning
    `_validate` already relies on.

    A player who is not `ACTIVE` (injured, suspended, and similar) is only used when there
    are not enough available players for that position: preferred over leaving the slot
    empty, since an empty slot has a known, fixed cost (`POINTS_PER_EMPTY_SLOT`) while even
    an unavailable player might score something.

    If `tactic` is omitted, all five formations Comunio accepts are evaluated and the one
    with the highest points net of the empty-slot penalty wins, ties broken by fewest empty
    slots and then by formation name — so the result is reproducible for the same squad.
    """
    if tactic is not None and tactic not in TACTICS:
        raise LineupError(
            f"{tactic!r} is not a formation Comunio accepts. Valid: "
            + ", ".join(sorted(TACTICS))
        )

    by_position: dict[str, list[SquadPlayer]] = {}
    for player in players:
        by_position.setdefault(player.position, []).append(player)

    candidates = [tactic] if tactic else sorted(TACTICS)
    plans = [_plan_for_tactic(by_position, candidate) for candidate in candidates]
    plans.sort(
        key=lambda plan: (
            -(plan.estimated_points - plan.penalty_points),
            plan.empty_slots,
            plan.tactic,
        )
    )
    return plans[0]
