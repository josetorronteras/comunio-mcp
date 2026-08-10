import json
from datetime import datetime

import pytest

from comunio_mcp.comunio.squad import parse_squad
from tests.conftest import MANAGER_NAME


@pytest.fixture
def squad(squad_response):
    return parse_squad(squad_response)


def test_every_player_is_parsed(squad):
    assert len(squad.players) == 8
    assert squad.tactic == "442"
    assert squad.owner == MANAGER_NAME


def test_a_dash_means_no_points_yet(squad):
    # `points` is "-" until the season has produced any.
    assert all(player.points is None for player in squad.players)


def test_last_points_survives_both_a_numeric_string_and_null(squad):
    by_name = {player.name: player for player in squad.players}

    assert by_name["Portero Dos"].last_points == 4
    assert by_name["Portero Uno"].last_points is None


def test_average_points_survives_an_inconsistent_type(squad):
    # The API sends "0" for one player and 3.5 for another, in the same response.
    by_name = {player.name: player for player in squad.players}

    assert by_name["Portero Uno"].average_points == 0.0
    assert by_name["Delantero Uno"].average_points == 3.5


def test_the_recommended_price_sentinel_becomes_none(squad):
    by_name = {player.name: player for player in squad.players}

    # -1 means Comunio has no recommendation, not a price of minus one euro.
    assert by_name["Portero Uno"].recommended_price is None
    assert by_name["Portero Dos"].recommended_price == 450_000


def test_an_empty_lineup_slot_becomes_none(squad):
    by_name = {player.name: player for player in squad.players}

    assert by_name["Portero Uno"].lineup_slot == "1"
    assert by_name["Defensa Tres"].lineup_slot is None


def test_injuries_come_through_with_their_reason(squad):
    injured = [p for p in squad.players if p.status != "ACTIVE"]

    assert len(injured) == 1
    assert injured[0].status == "WEAKENED"
    assert injured[0].status_info == "Lesión muscular"


def test_an_active_player_has_no_status_info(squad):
    by_name = {player.name: player for player in squad.players}

    assert by_name["Portero Uno"].status_info is None


def test_the_next_match_is_flattened_to_the_two_club_names(squad):
    match = {p.name: p for p in squad.players}["Portero Uno"].next_match

    assert match is not None
    assert match.home == "Mock FC"
    assert match.away == "Rival FC"
    assert match.kickoff == datetime.fromisoformat("2026-08-15T19:30:00+02:00")


def test_a_player_without_a_fixture_has_no_next_match(squad):
    by_name = {player.name: player for player in squad.players}

    assert by_name["Medio Uno"].next_match is None


def test_the_summary_counts_what_lineup_rules_need(squad):
    summary = squad.summary

    assert summary.total == 8
    assert summary.lined_up == 4
    assert summary.substitutes == 1
    assert summary.unavailable == 1
    assert summary.on_market == 2
    assert summary.by_position == {"keeper": 2, "defender": 3, "midfielder": 2, "striker": 1}


def test_link_clutter_is_dropped(squad):
    serialised = json.dumps(squad.model_dump(mode="json"), ensure_ascii=False)

    for noise in ("_links", "photo", "logo", "purchaseInfo", "wasLiveSubstituted"):
        assert noise not in serialised


def test_an_empty_squad_does_not_crash():
    squad = parse_squad({"items": [], "tactic": ""})

    assert squad.players == []
    assert squad.owner is None
    assert squad.summary.total == 0
