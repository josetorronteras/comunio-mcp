import json
from datetime import datetime

import pytest

from comunio_mcp.comunio.player import parse_player
from comunio_mcp.comunio.statuses import MEANINGS, meaning
from tests.conftest import MANAGER_NAME


@pytest.fixture
def player(player_response):
    return parse_player(player_response)


def test_the_basics_are_parsed(player):
    assert player.player_id == 1400
    assert player.name == "Jugador Detalle"
    assert player.club.name == "Mock FC"
    assert player.price == 4_750_000


def test_a_status_code_is_translated_and_availability_derived(player):
    # The API sends the bare code and nothing else.
    assert player.status == "YELLOW_RED_BANNED"
    assert player.status_meaning == "suspended after a second yellow"
    assert player.available is False


def test_the_dash_is_still_the_dash(player):
    assert player.total_points is None
    assert player.last_points == 4


def test_averages_survive_being_strings_and_blanks(player):
    assert player.averages.grade == 2.8
    assert player.averages.points == 6.4
    # Before any match is graded the recent window comes back empty rather than zero.
    assert player.averages.recent_grade is None
    assert player.averages.recent_points is None


def test_the_record_is_flattened_from_two_objects(player):
    record = player.record

    assert record.played == 34
    assert record.goals == 12
    assert record.man_of_the_match == 5
    assert record.yellow_red_cards == 1
    assert record.red_cards == 0


def test_season_history_is_kept(player):
    assert [(s.season, s.points) for s in player.history] == [("25/26", 212), ("24/25", 198)]


def test_the_buyout_clause_comes_through(player):
    clause = player.buyout_clause

    # What taking the player from their owner without consent would cost.
    assert clause.price == 9_500_000
    assert clause.paid is False
    assert clause.block_days == 3


def test_the_purchase_price_is_kept(player):
    assert player.purchase_price == 4_200_000
    assert player.owner == MANAGER_NAME


def test_upcoming_fixtures_are_flattened(player):
    assert len(player.next_matches) == 2
    first = player.next_matches[0]

    assert (first.home, first.away) == ("Mock FC", "Rival FC")
    assert first.kickoff == datetime.fromisoformat("2026-08-15T19:30:00+02:00")


def test_an_empty_preferred_foot_becomes_none(player):
    assert player.profile.preferred_foot is None
    assert player.profile.shirt_number == 13


def test_marketing_links_are_dropped(player):
    serialised = json.dumps(player.model_dump(mode="json"), ensure_ascii=False)

    for noise in ("externalLinks", "example.invalid", "blogTag", "communityId", "inLineup"):
        assert noise not in serialised


def test_every_documented_status_has_a_meaning():
    # Thirteen values, recovered from the web app's translation table. The API had only
    # ever shown four of them.
    assert len(MEANINGS) == 13
    assert all(meaning(code) for code in MEANINGS)


def test_a_past_status_reads_as_past_tense():
    assert meaning("WAS_INJURED") == "was injured"


def test_an_unknown_status_passes_through_untranslated():
    # Status is an open set, so a code we have not seen must not raise.
    assert meaning("SOMETHING_NEW") is None
    assert meaning(None) is None
