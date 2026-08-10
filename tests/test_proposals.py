from datetime import UTC, datetime, timedelta

import pytest

from comunio_mcp.proposals import DEFAULT_TTL, ProposalError, ProposalStore

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

BID = {"player_id": 3871, "price": 810_000, "type": "NEW"}


@pytest.fixture
def store(tmp_path):
    store = ProposalStore(tmp_path / "state" / "proposals.sqlite3")
    yield store
    store.close()


def _bid(store, *, now=NOW, ttl=DEFAULT_TTL):
    return store.create(
        kind="bid", summary="Bid €810,000 for player 3871", payload=BID, ttl=ttl, now=now
    )


def test_a_proposal_round_trips(store):
    created = _bid(store)

    fetched = store.get(created.id)

    assert fetched is not None
    assert fetched.kind == "bid"
    assert fetched.payload == BID
    assert fetched.summary == "Bid €810,000 for player 3871"
    assert fetched.claimed_at is None


def test_the_store_creates_its_directory(tmp_path):
    # The state directory is a mounted volume in production and may not exist yet.
    store = ProposalStore(tmp_path / "missing" / "deeper" / "proposals.sqlite3")
    store.create(kind="bid", summary="s", payload={}, now=NOW)
    store.close()

    assert (tmp_path / "missing" / "deeper" / "proposals.sqlite3").exists()


def test_ids_are_unique(store):
    ids = {_bid(store).id for _ in range(20)}

    assert len(ids) == 20


def test_claiming_returns_exactly_what_was_proposed(store):
    created = _bid(store)

    claimed = store.claim(created.id, now=NOW)

    # An execution applies the stored proposal, so it cannot differ from what was shown.
    assert claimed.payload == BID
    assert claimed.summary == created.summary
    assert claimed.claimed_at == NOW


def test_a_proposal_can_only_be_executed_once(store):
    created = _bid(store)
    store.claim(created.id, now=NOW)

    # The whole point: a repeated call must lose rather than place the bid twice.
    with pytest.raises(ProposalError) as excinfo:
        store.claim(created.id, now=NOW)

    assert "already executed" in str(excinfo.value)


def test_an_expired_proposal_is_refused(store):
    created = _bid(store, ttl=timedelta(minutes=5))

    with pytest.raises(ProposalError) as excinfo:
        store.claim(created.id, now=NOW + timedelta(minutes=6))

    assert "expired" in str(excinfo.value)


def test_a_proposal_is_still_good_just_before_it_expires(store):
    created = _bid(store, ttl=timedelta(minutes=5))

    claimed = store.claim(created.id, now=NOW + timedelta(minutes=4, seconds=59))

    assert claimed.claimed_at is not None


def test_an_unknown_id_is_refused(store):
    with pytest.raises(ProposalError) as excinfo:
        store.claim("nope", now=NOW)

    assert "No proposal" in str(excinfo.value)


def test_a_proposal_of_the_wrong_kind_is_refused(store):
    created = _bid(store)

    # Stops execute_lineup from applying a bid proposal.
    with pytest.raises(ProposalError) as excinfo:
        store.claim(created.id, kind="lineup", now=NOW)

    assert "not a lineup one" in str(excinfo.value)
    assert store.get(created.id).claimed_at is None


def test_the_outcome_is_recorded_for_audit(store):
    created = _bid(store)
    store.claim(created.id, now=NOW)

    store.record_outcome(created.id, {"status": "OK", "offer_id": 1314490087})

    assert store.get(created.id).outcome == {"status": "OK", "offer_id": 1314490087}


def test_pending_lists_only_what_is_still_usable(store):
    live = _bid(store)
    claimed = _bid(store)
    stale = _bid(store, ttl=timedelta(minutes=5))
    store.claim(claimed.id, now=NOW)

    pending = store.pending(now=NOW + timedelta(minutes=6))

    assert [p.id for p in pending] == [live.id]
    assert stale.id not in {p.id for p in pending}


def test_purge_drops_stale_proposals_but_keeps_executed_ones(store):
    executed = _bid(store, ttl=timedelta(minutes=5))
    stale = _bid(store, ttl=timedelta(minutes=5))
    store.claim(executed.id, now=NOW)

    removed = store.purge(before=NOW + timedelta(hours=1))

    assert removed == 1
    assert store.get(stale.id) is None
    # The audit trail outlives the proposal's usefulness.
    assert store.get(executed.id) is not None


def test_proposals_survive_reopening_the_file(tmp_path):
    path = tmp_path / "proposals.sqlite3"
    first = ProposalStore(path)
    created = first.create(kind="bid", summary="s", payload=BID, now=NOW)
    first.close()

    second = ProposalStore(path)
    try:
        assert second.get(created.id).payload == BID
    finally:
        second.close()
