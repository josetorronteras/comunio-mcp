import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.standings import fetch_standings, parse_standings
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, MANAGER_NAME, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


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


@pytest.fixture
def live(standings_live_response):
    return parse_standings(standings_live_response, me=USER_ID)


def test_the_live_period_carries_points_being_scored_right_now(live):
    by_name = {row.manager: row for row in live.rows}

    assert live.period == "live"
    assert by_name[MANAGER_NAME].live_points == 6
    assert by_name[MANAGER_NAME].players_possibly_scoring == 1
    # Zero is an answer — nobody of theirs is playing — and is not the same as null.
    assert by_name["Rival Dos"].live_points == 0


def test_a_null_figure_is_read_as_zero(standings_live_response):
    # The real `live` payload sends these keys present but null, which a `.get` default
    # does not cover: the default only fires on a missing key. `totalPerennialPoints`
    # arriving null used to fail model validation and made the whole period unusable.
    nulled = json.loads(json.dumps(standings_live_response))
    nulled["items"][0].update(
        {
            "totalPoints": None,
            "totalPerennialPoints": None,
            "playersPossiblyScoredAmount": None,
        }
    )
    nulled["items"][0]["_embedded"]["teamInfo"]["teamValue"] = None
    nulled["items"][0]["_embedded"]["user"]["negativeBudget"] = None

    row = parse_standings(nulled, me=USER_ID).rows[0]

    assert row.total_points == 0
    assert row.perennial_points == 0
    assert row.players_possibly_scoring == 0
    assert row.team_value == 0
    assert row.negative_budget is False


def test_only_the_live_period_reports_who_is_broke(standings, live):
    # Under `total` the flag reads false for every manager, so a table asked for that way
    # cannot be used to tell who will score nothing this matchday.
    broke_now = [row.manager for row in live.rows if row.negative_budget]

    assert broke_now == ["Rival Tres"]
    assert [row.manager for row in standings.rows if row.negative_budget] != broke_now


class FakeApi:
    """Answers login, the index and the standings endpoint."""

    def __init__(self, payload) -> None:
        self.payload = payload
        self.requested: list[str] = []

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
                        "game:standings": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/standings"
                        }
                    },
                },
            )

        self.requested.append(str(request.url))
        return httpx2.Response(200, json=self.payload)


def _run(handler, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(Session(client), client)

    return asyncio.run(run())


def test_the_season_table_is_what_gets_asked_for_by_default(standings_response):
    handler = FakeApi(standings_response)

    _run(handler, lambda s, c: fetch_standings(s, c))

    assert "period=total" in handler.requested[0]
    # Undocumented, but the endpoint answers with something that is not JSON without it.
    assert "wpe=true" in handler.requested[0]


def test_the_live_period_is_passed_through(standings_live_response):
    handler = FakeApi(standings_live_response)

    _run(handler, lambda s, c: fetch_standings(s, c, period="live"))

    assert "period=live" in handler.requested[0]
