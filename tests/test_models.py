import json

from comunio_mcp.comunio.session import _parse_snapshot
from tests.conftest import LEAGUE_NAME, MANAGER_NAME


def test_snapshot_parses_the_payload_shape(index_response):
    snapshot = _parse_snapshot(index_response)

    assert snapshot.account.name == MANAGER_NAME
    assert snapshot.community.name == LEAGUE_NAME
    assert snapshot.account.tactic == "433"


def test_numeric_strings_become_numbers(index_response):
    account = _parse_snapshot(index_response).account

    # The API sends "15000000"; arithmetic on a string would silently concatenate.
    assert account.budget == 15_000_000
    assert account.team_value == 42_500_000
    assert account.team_count == 18
    assert account.team_count_linedup == 11
    assert isinstance(account.budget, int)


def test_rules_are_unwrapped_from_their_items_envelope(index_response):
    rules = _parse_snapshot(index_response).community.rules

    assert rules.second_highest_offers is False
    assert rules.members == 8
    assert rules.tradables_on_exchangemarket == 10
    assert rules.creditfactor == "dynamic"


def test_an_empty_optional_rule_becomes_none(index_response):
    # `max_tradables_per_user` arrives as "" when the league sets no cap.
    rules = _parse_snapshot(index_response).community.rules

    assert rules.max_tradables_per_user is None


def test_personal_data_never_reaches_the_model(index_response):
    snapshot = _parse_snapshot(index_response)

    serialised = json.dumps(snapshot.model_dump(), ensure_ascii=False)

    for secret in ("mock@example.invalid", "FAKE-INVITE==", "FAKE-PPID=="):
        assert secret not in serialised
    for field in ("email", "invitationCode", "ppidGoogle", "lastAction", "firstName", "password"):
        assert field not in serialised


def test_unknown_fields_are_dropped_rather_than_kept(index_response):
    # An allowlist: a field Comunio adds tomorrow must not leak through.
    payload = json.loads(json.dumps(index_response))
    payload["user"]["phoneNumber"] = "+34600000000"

    serialised = json.dumps(_parse_snapshot(payload).model_dump())

    assert "phoneNumber" not in serialised
    assert "+34600000000" not in serialised
