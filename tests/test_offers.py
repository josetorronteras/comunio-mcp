import json

import pytest

from comunio_mcp.comunio.offers import parse_offers
from tests.conftest import MANAGER_NAME, USER_ID


@pytest.fixture
def offers(offers_response):
    return parse_offers(offers_response, me=USER_ID)


def test_every_offer_is_parsed(offers):
    assert len(offers.offers) == 3
    assert offers.has_more is False


def test_credit_is_not_the_budget(offers):
    # The league's dynamic credit factor means spending power exceeds cash in hand.
    # Sizing a bid against the budget instead of this would understate what is possible.
    assert offers.credit == 29_475_000


def test_direction_is_worked_out_from_who_made_the_offer(offers):
    by_id = {offer.offer_id: offer for offer in offers.offers}

    assert by_id[9000001].direction == "incoming"
    assert by_id[9000003].direction == "outgoing"


def test_an_offer_above_market_value_has_a_positive_premium(offers):
    offer = {o.offer_id: o for o in offers.offers}[9000001]

    assert offer.premium == 9_000
    assert offer.premium_pct == 2.1


def test_an_offer_below_market_value_has_a_negative_premium(offers):
    # 3,528,400 for a player quoted at 3,630,000. Accepting it loses value.
    offer = {o.offer_id: o for o in offers.offers}[9000002]

    assert offer.premium == -101_600
    assert offer.premium_pct == -2.8


def test_computer_offers_are_flagged(offers):
    from_computer = [offer.offer_id for offer in offers.offers if offer.from_computer]

    assert from_computer == [9000001, 9000002]


def test_names_are_stripped_of_padding(offers):
    # Comunio pads some manager names with a trailing space.
    outgoing = [offer for offer in offers.offers if offer.direction == "outgoing"][0]

    assert outgoing.offered_by == MANAGER_NAME
    assert outgoing.counterparty == "Rival Uno"


def test_the_summary_separates_the_two_directions(offers):
    summary = offers.summary

    assert summary.total == 3
    assert summary.incoming == 2
    assert summary.outgoing == 1
    assert summary.from_computer == 2
    assert summary.below_quoted == 1
    # What accepting every incoming offer would bring in.
    assert summary.incoming_total == 439_000 + 3_528_400


def test_the_player_is_flattened_and_clutter_dropped(offers):
    offer = offers.offers[0]

    assert offer.player.name == "Medio Uno"
    assert offer.player.club.name == "Mock FC"

    serialised = json.dumps(offers.model_dump(mode="json"), ensure_ascii=False)
    for noise in ("_links", "photo", "purchasePrice", "displayName", "tradablesOffered"):
        assert noise not in serialised


def test_no_offers_does_not_crash():
    offers = parse_offers({"credit": 0, "items": None}, me=USER_ID)

    assert offers.offers == []
    assert offers.summary.incoming_total == 0
