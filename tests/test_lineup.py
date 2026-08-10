import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.lineup import LineupError, best_lineup, set_lineup, slot_plan
from comunio_mcp.comunio.models import Club, SquadPlayer
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")

KEEPER_ID, DEF_1, DEF_2, DEF_3, MID_1, STR_1, INJURED_ID = 1, 2, 3, 4, 5, 6, 7


def _squad_player(player_id, name, position, status="ACTIVE"):
    return {
        "id": player_id,
        "name": name,
        "club": {"id": 1, "name": "Mock FC"},
        "position": position,
        "status": status,
        "statusInfo": "",
        "points": "-",
        "lastPoints": None,
        "averagePoints": 0,
        "matchdayPoints": 0,
        "pos": "",
        "quotedprice": 1000,
        "recommendedprice": -1,
        "linedup": False,
        "substitute": False,
        "onMarket": False,
        "isExchangeable": False,
        "hasAcceptedOffers": False,
        "motm": False,
        "watched": False,
        "nextMatch": None,
        "owner": {"id": int(USER_ID), "name": "MOCK MANAGER"},
    }


SQUAD = {
    "items": [
        _squad_player(KEEPER_ID, "Portero", "keeper"),
        _squad_player(DEF_1, "Defensa Uno", "defender"),
        _squad_player(DEF_2, "Defensa Dos", "defender"),
        _squad_player(DEF_3, "Defensa Tres", "defender"),
        _squad_player(MID_1, "Medio Uno", "midfielder"),
        _squad_player(STR_1, "Delantero Uno", "striker"),
        _squad_player(INJURED_ID, "Medio Roto", "midfielder", status="INJURED"),
    ],
    "tactic": "343",
}


class FakeApi:
    def __init__(self, *, response=None) -> None:
        self.writes: list[httpx2.Request] = []
        self.response = response or {"status": "OK"}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login":
            return httpx2.Response(
                200,
                json={
                    "access_token": "a",
                    "expires_in": 1800,
                    "token_type": "Bearer",
                    "scope": "",
                    "refresh_token": "r",
                },
            )
        if request.url.path == "/":
            return httpx2.Response(
                200,
                json={
                    "user": {"id": USER_ID},
                    "community": {"id": COMMUNITY_ID},
                    "_links": {
                        "game:squad": {"href": "https://api.comunio.es/users/:userId/squad"},
                        "game:lineup": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/lineup"
                        },
                    },
                },
            )
        if request.url.path.endswith("/squad"):
            return httpx2.Response(200, json=SQUAD)

        self.writes.append(request)
        return httpx2.Response(200, json=self.response)


def _run(handler, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(Session(client), client)

    return asyncio.run(run())


def test_the_slot_plan_puts_the_keeper_last_and_strikers_first():
    # Deduced from two real lineups: 11 is always the keeper, slot 1 a striker.
    assert slot_plan("343") == [
        (1, "striker"), (2, "striker"), (3, "striker"),
        (4, "midfielder"), (5, "midfielder"), (6, "midfielder"), (7, "midfielder"),
        (8, "defender"), (9, "defender"), (10, "defender"),
        (11, "keeper"),
    ]


def test_the_slot_plan_shifts_with_the_formation():
    assert slot_plan("442")[0] == (1, "striker")
    assert slot_plan("442")[2] == (3, "midfielder")
    assert slot_plan("442")[-1] == (11, "keeper")


def test_a_lineup_is_sent_with_slots_worked_out_from_positions():
    handler = FakeApi()

    result = _run(
        handler,
        lambda s, c: set_lineup(
            s, c, tactic="343", keeper=KEEPER_ID,
            defenders=[DEF_1, DEF_2, DEF_3], midfielders=[MID_1], strikers=[STR_1],
        ),
    )

    request = handler.writes[0]
    assert request.method == "PUT"
    body = json.loads(request.content)
    assert body["tactic"] == "343"
    assert body["type"] == "default"
    assert body["userId"] == int(USER_ID)
    # Ids go as strings, empty slots as empty strings.
    assert body["lineup"]["1"] == str(STR_1)
    assert body["lineup"]["4"] == str(MID_1)
    assert body["lineup"]["8"] == str(DEF_1)
    assert body["lineup"]["11"] == str(KEEPER_ID)
    assert body["lineup"]["2"] == ""
    assert result.ok is True


def test_an_incomplete_lineup_reports_what_it_costs():
    handler = FakeApi()

    result = _run(
        handler,
        lambda s, c: set_lineup(s, c, tactic="343", keeper=KEEPER_ID, strikers=[STR_1]),
    )

    # Nine of eleven slots empty, at Comunio's stated four points each.
    assert result.empty_slots == 9
    assert result.penalty_points == 36


def test_an_unavailable_player_is_reported_but_not_refused():
    # Comunio permits fielding an injured player, so this warns rather than blocks.
    handler = FakeApi()

    result = _run(
        handler,
        lambda s, c: set_lineup(s, c, tactic="343", midfielders=[INJURED_ID]),
    )

    assert result.unavailable == ["Medio Roto"]
    assert result.ok is True


def test_an_unknown_formation_is_refused_before_anything_is_sent():
    handler = FakeApi()

    with pytest.raises(LineupError) as excinfo:
        _run(handler, lambda s, c: set_lineup(s, c, tactic="4231", keeper=KEEPER_ID))

    assert "not a formation" in str(excinfo.value)
    assert handler.writes == []


def test_too_many_players_for_the_formation_is_refused():
    handler = FakeApi()

    with pytest.raises(LineupError) as excinfo:
        _run(
            handler,
            lambda s, c: set_lineup(
                s, c, tactic="352", defenders=[DEF_1, DEF_2, DEF_3, KEEPER_ID]
            ),
        )

    assert "room for 3" in str(excinfo.value)
    assert handler.writes == []


def test_a_player_out_of_position_is_refused():
    handler = FakeApi()

    with pytest.raises(LineupError) as excinfo:
        _run(handler, lambda s, c: set_lineup(s, c, tactic="343", strikers=[DEF_1]))

    assert "cannot be played at striker" in str(excinfo.value)
    assert handler.writes == []


def test_the_same_player_twice_is_refused():
    handler = FakeApi()

    with pytest.raises(LineupError) as excinfo:
        _run(
            handler,
            lambda s, c: set_lineup(s, c, tactic="343", defenders=[DEF_1, DEF_1, DEF_2]),
        )

    assert "two slots" in str(excinfo.value)
    assert handler.writes == []


def test_someone_outside_the_squad_is_refused():
    handler = FakeApi()

    with pytest.raises(LineupError) as excinfo:
        _run(handler, lambda s, c: set_lineup(s, c, tactic="343", strikers=[999]))

    assert "Not in the squad" in str(excinfo.value)
    assert handler.writes == []


def _player(player_id, name, position, *, average_points=0.0, status="ACTIVE"):
    return SquadPlayer(
        id=player_id,
        name=name,
        club=Club(id=1, name="Mock FC"),
        position=position,
        status=status,
        points=None,
        last_points=None,
        average_points=average_points,
        matchday_points=None,
        motm=False,
        linedup=False,
        substitute=False,
        quoted_price=1000,
        on_market=False,
        is_exchangeable=False,
        has_accepted_offers=False,
        watched=False,
    )


def test_best_lineup_fills_a_fixed_tactic_ranked_by_average_points():
    keeper = _player(1, "Portero", "keeper", average_points=5)
    defenders = [
        _player(2, "Defensa Uno", "defender", average_points=9),
        _player(3, "Defensa Dos", "defender", average_points=8),
        _player(4, "Defensa Tres", "defender", average_points=7),
        _player(5, "Defensa Roto", "defender", average_points=1, status="INJURED"),
    ]
    midfielders = [
        _player(6, "Medio Uno", "midfielder", average_points=10),
        _player(7, "Medio Dos", "midfielder", average_points=9),
        _player(8, "Medio Roto", "midfielder", average_points=2, status="INJURED"),
    ]
    striker = _player(9, "Delantero Uno", "striker", average_points=12)

    plan = best_lineup([keeper, *defenders, *midfielders, striker], tactic="442")

    fielded_ids = {player.id for _, _, player in plan.fielded}
    # All four defenders used, including the injured one: only three are ACTIVE.
    assert fielded_ids >= {2, 3, 4, 5}
    # All three midfielders used: even with the injured one, the formation needs four.
    assert fielded_ids >= {6, 7, 8}
    assert plan.tactic == "442"
    # 2 strikers needed, only 1 exists; 4 midfielders needed, only 3 exist.
    assert plan.empty_slots == 2
    assert plan.penalty_points == 8
    assert plan.estimated_points == 63.0
    assert plan.payload == {
        "tactic": "442",
        "keeper": 1,
        "defenders": [2, 3, 4, 5],
        "midfielders": [6, 7, 8],
        "strikers": [9],
    }


def test_best_lineup_prefers_active_players_over_injured_ones():
    active = _player(1, "Sano", "midfielder", average_points=1)
    injured = _player(2, "Roto", "midfielder", average_points=99, status="INJURED")

    plan = best_lineup(
        [_player(10, "Portero", "keeper"), active, injured], tactic="442"
    )

    midfielder_ids = [p.id for _, position, p in plan.fielded if position == "midfielder"]
    assert midfielder_ids[0] == active.id  # ranked first despite the lower average


def test_best_lineup_auto_selects_the_formation_with_no_empty_slots():
    keeper = _player(1, "Portero", "keeper", average_points=5)
    defenders = [_player(i, f"Defensa {i}", "defender", average_points=10 - i) for i in (2, 3, 4)]
    midfielders = [
        _player(i, f"Medio {i}", "midfielder", average_points=10 - i) for i in (5, 6, 7, 8, 9)
    ]
    strikers = [_player(10, "Delantero Uno", "striker", average_points=12),
                _player(11, "Delantero Dos", "striker", average_points=11)]

    # Exactly matches 352 (3 defenders, 5 midfielders, 2 strikers): no formation with more
    # slots for any position could do better, since there is nobody left to fill them.
    plan = best_lineup([keeper, *defenders, *midfielders, *strikers])

    assert plan.tactic == "352"
    assert plan.empty_slots == 0


def test_best_lineup_leaves_a_slot_empty_when_nobody_is_left_to_fill_it():
    plan = best_lineup([_player(1, "Portero", "keeper")], tactic="343")

    assert plan.empty_slots == 10
    assert plan.penalty_points == 40
    assert plan.payload == {
        "tactic": "343", "keeper": 1, "defenders": [], "midfielders": [], "strikers": [],
    }


def test_best_lineup_ties_break_on_player_id_for_reproducibility():
    lower_id = _player(1, "A", "striker", average_points=5)
    higher_id = _player(2, "B", "striker", average_points=5)

    first = best_lineup([_player(3, "K", "keeper"), lower_id, higher_id], tactic="442")
    second = best_lineup([_player(3, "K", "keeper"), lower_id, higher_id], tactic="442")

    assert first.payload == second.payload
    assert first.payload["strikers"][0] == higher_id.id


def test_best_lineup_refuses_an_unknown_formation():
    with pytest.raises(LineupError, match="not a formation"):
        best_lineup([_player(1, "Portero", "keeper")], tactic="4231")
