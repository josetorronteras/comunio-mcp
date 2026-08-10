import json
from datetime import datetime

import pytest

from comunio_mcp.comunio.transfers import _summarise, parse_transfer_entries
from tests.conftest import MANAGER_NAME, USER_ID


@pytest.fixture
def transfers(news_entries):
    return parse_transfer_entries(news_entries, me=USER_ID)


def test_only_transfer_entries_are_kept(transfers, news_entries):
    # Four news entries, one of which is a transfer digest holding three moves.
    assert len(news_entries) == 4
    assert len(transfers) == 3


def test_the_marketing_html_never_survives(transfers):
    serialised = json.dumps([t.model_dump(mode="json") for t in transfers], ensure_ascii=False)

    # A single promotional entry in this feed is longer than every transfer in it.
    assert "marketing" not in serialised
    assert "<p>" not in serialised


def test_both_buckets_are_read(transfers):
    kinds = sorted({transfer.kind for transfer in transfers})

    assert kinds == ["FROM_COMPUTER", "TO_COMPUTER"]


def test_buying_from_the_computer_is_flagged(transfers):
    bought = [t for t in transfers if t.from_computer]

    assert len(bought) == 2
    assert all(t.to_computer is False for t in bought)


def test_selling_to_the_computer_is_flagged(transfers):
    sold = [t for t in transfers if t.to_computer]

    assert len(sold) == 1
    assert sold[0].price == 659_100
    assert sold[0].immediate_at == "06:52"


def test_the_managers_own_deals_are_marked(transfers):
    mine = [t for t in transfers if t.involves_me]

    assert len(mine) == 1
    assert mine[0].to_manager == MANAGER_NAME
    assert mine[0].price == 1_650_020


def test_names_are_stripped(transfers):
    sold = [t for t in transfers if t.to_computer][0]

    assert sold.from_manager == "Rival Dos"


def test_the_digest_date_is_carried_onto_every_move(transfers):
    assert all(
        t.date == datetime.fromisoformat("2026-08-10T04:30:27+02:00") for t in transfers
    )


def test_an_unknown_bucket_is_parsed_rather_than_dropped():
    # Only FROM_COMPUTER and TO_COMPUTER have been observed, but a manager-to-manager
    # deal presumably arrives under some third key. Losing it silently would be worse
    # than not knowing its name, so buckets are read generically.
    entry = {
        "date": "2026-08-10T04:30:27+02:00",
        "type": "TRANSACTION_TRANSFER",
        "message": {
            "SOME_FUTURE_BUCKET": [
                {
                    "tradable": {"id": 1, "name": "Traspaso"},
                    "from": {"id": 30000001, "name": "Rival Uno"},
                    "to": {"id": 30000002, "name": "Rival Dos"},
                    "price": 500_000,
                }
            ]
        },
    }

    transfers = parse_transfer_entries([entry], me=USER_ID)

    assert len(transfers) == 1
    assert transfers[0].kind == "SOME_FUTURE_BUCKET"
    assert transfers[0].from_computer is False
    assert transfers[0].to_computer is False


def test_a_malformed_message_is_skipped():
    entry = {"date": "2026-08-10T04:30:27+02:00", "type": "TRANSACTION_TRANSFER", "message": None}

    assert parse_transfer_entries([entry], me=USER_ID) == []


def test_the_summary_counts_each_kind(transfers):
    summary = _summarise(transfers, me=USER_ID)

    assert summary.total == 3
    assert summary.between_managers == 0
    assert summary.bought_from_computer == 2
    assert summary.sold_to_computer == 1
    assert summary.mine == 1
    assert summary.total_value == 7_100_000 + 1_650_020 + 659_100
