import json

import pytest

from comunio_mcp.comunio.standings import parse_standings
from tests.conftest import MANAGER_NAME, USER_ID


@pytest.fixture
def standings(standings_response):
    return parse_standings(standings_response, me=USER_ID)


def test_every_manager_is_parsed(standings):
    assert standings.period == "total"
    assert [row.manager for row in standings.rows] == [
        "Rival Uno",
        "Rival Dos",
        MANAGER_NAME,
        "Rival Tres",
    ]


def test_rank_comes_from_the_order_not_the_payload(standings):
    # Every `position` in the payload is 0 before the season starts, so the field is
    # useless and rank is derived from the order Comunio sends.
    assert [row.rank for row in standings.rows] == [1, 2, 3, 4]


def test_the_signed_in_manager_is_marked(standings):
    mine = [row for row in standings.rows if row.is_me]

    assert len(mine) == 1
    assert mine[0].manager == MANAGER_NAME
    assert mine[0].rank == 3


def test_a_dash_means_no_points_last_matchday(standings):
    by_name = {row.manager: row for row in standings.rows}

    assert by_name["Rival Uno"].last_points == 7
    assert by_name["Rival Dos"].last_points is None


def test_embedded_team_and_user_are_flattened(standings):
    by_name = {row.manager: row for row in standings.rows}

    assert by_name["Rival Uno"].team_value == 54_750_000
    assert by_name["Rival Uno"].manager_id == 30000001


def test_negative_budget_is_surfaced(standings):
    broke = [row.manager for row in standings.rows if row.negative_budget]

    # Who cannot outbid you is market intelligence, not trivia.
    assert broke == ["Rival Dos"]


def test_third_party_personal_data_is_dropped(standings):
    serialised = json.dumps(standings.model_dump(), ensure_ascii=False)

    for secret in ("secret-login", "Real Name"):
        assert secret not in serialised
    for field in ("login", "firstName", "blocked", "leagueId", "badges", "_embedded"):
        assert field not in serialised


def test_an_empty_table_does_not_crash():
    standings = parse_standings({"id": "total", "items": None}, me=USER_ID)

    assert standings.rows == []


def test_manager_names_are_stripped(standings_response):
    padded = json.loads(json.dumps(standings_response))
    padded["items"][0]["_embedded"]["user"]["name"] = "Rival Uno "

    standings = parse_standings(padded, me=USER_ID)

    # Offers and transfers strip too; without this the same manager fails to match
    # across tools.
    assert standings.rows[0].manager == "Rival Uno"
