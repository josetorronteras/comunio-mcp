import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.lineup import LineupError, set_lineup, slot_plan
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


def test_a_player_out_of_position_is_reported_not_refused():
    # Comunio lets a manager field the injured and the suspended, so it is not this
    # server's place to invent a positional rule the game may not have. It goes, and the
    # result says who was played out of position.
    handler = FakeApi()

    result = _run(handler, lambda s, c: set_lineup(s, c, tactic="343", strikers=[DEF_1]))

    assert handler.writes != []
    assert result.out_of_position == ["Defensa Uno is a defender played at striker"]


def test_a_lineup_in_position_reports_nothing_out_of_position():
    handler = FakeApi()

    result = _run(handler, lambda s, c: set_lineup(s, c, tactic="343", keeper=KEEPER_ID))

    assert result.out_of_position == []


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
