import json
from datetime import datetime

import pytest

from comunio_mcp.comunio.market import parse_market
from tests.conftest import MANAGER_NAME, USER_ID


@pytest.fixture
def market(market_response):
    return parse_market(market_response, me=USER_ID)


def test_every_listing_is_parsed(market):
    assert len(market.listings) == 5
    assert market.daily_transfers_processed is True


def test_the_deadline_is_surfaced(market):
    # Bids have to be in before the transfer round runs.
    assert market.closes_at == datetime.fromisoformat("2026-08-11T03:00:00+02:00")


def test_an_offset_without_a_colon_still_parses(market):
    # This endpoint writes "+0200"; everywhere else it is "+02:00".
    assert market.listings[0].listed_at == datetime.fromisoformat("2026-08-10T04:15:06+02:00")


def test_prices_use_the_capitalised_aliases(market):
    # `quotedPrice` here, `quotedprice` in the squad endpoint. Same concept, and the
    # aliases are not interchangeable.
    listing = market.listings[0]

    assert listing.quoted_price == 2_650_000
    assert listing.recommended_price == 2_650_000


def test_computer_listings_are_flagged(market):
    computer = [listing.name for listing in market.listings if listing.from_computer]

    # User id 1 is Comunio itself. Buying from it is not a negotiation with a rival.
    assert computer == ["Delantero Caro", "Defensa Barato"]


def test_the_managers_own_listings_are_flagged(market):
    mine = [listing.name for listing in market.listings if listing.is_mine]

    assert mine == ["Medio Propio", "Medio Lesionado"]
    assert all(listing.seller == MANAGER_NAME for listing in market.listings if listing.is_mine)


def test_a_rival_listing_is_neither_mine_nor_the_computers(market):
    rival = [listing for listing in market.listings if listing.seller == "Rival Uno"][0]

    assert rival.from_computer is False
    assert rival.is_mine is False
    assert rival.seller_id == 30000001


def test_price_trend_survives_including_negatives(market):
    by_name = {listing.name: listing for listing in market.listings}

    assert by_name["Medio Propio"].trend == -2
    assert by_name["Portero Rival"].trend == 4


def test_injuries_come_through(market):
    injured = [listing for listing in market.listings if listing.status != "ACTIVE"]

    assert len(injured) == 1
    assert injured[0].status_info == "Lesión muscular"


def test_the_summary_splits_by_seller_kind(market):
    summary = market.summary

    assert summary.total == 5
    assert summary.from_computer == 2
    assert summary.from_managers == 3
    assert summary.mine == 2
    assert summary.unavailable == 1
    assert summary.by_position == {"striker": 1, "defender": 1, "midfielder": 2, "keeper": 1}


def test_link_clutter_is_dropped(market):
    serialised = json.dumps(market.model_dump(mode="json"), ensure_ascii=False)

    for noise in ("_links", "_embedded", "photo", "purchasePrice", "communityId"):
        assert noise not in serialised


def test_an_empty_market_does_not_crash():
    market = parse_market({"items": [], "dailyTransfersProcessed": False}, me=USER_ID)

    assert market.listings == []
    assert market.closes_at is None
    assert market.summary.total == 0


def test_a_status_code_is_read_out_in_words(market):
    injured = [listing for listing in market.listings if listing.status != "ACTIVE"]

    assert injured[0].status_meaning == "carrying a knock"
    assert market.listings[0].status_meaning == "available"
