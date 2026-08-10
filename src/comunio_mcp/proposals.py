"""Where proposals live between being made and being executed.

Decision 2 says an `execute_*` tool applies a proposal the user has already seen, never a
set of arguments the model supplies on the spot. That requires somewhere to keep the
proposal, and MCP is a stateless *protocol*: nothing in a `tools/call` carries state from
the previous one.

Two properties matter more than anything else here:

* **A proposal can be executed at most once.** The claim is a single conditional UPDATE, so
  two concurrent executions cannot both win. Without that, a retried or repeated call
  places the same bid twice.
* **A proposal expires.** A lineup is meaningless after kick-off and a bid is meaningless
  once the transfer round has run, so a stale proposal must be refused rather than applied
  late.

What is stored is the *whole* proposal, including the summary the user was shown. An
execution then has no freedom to differ from what was approved.
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TTL = timedelta(minutes=30)

SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    summary     TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    claimed_at  TEXT,
    outcome     TEXT
);
"""


class ProposalError(RuntimeError):
    """A proposal cannot be used: unknown, expired, or already executed."""


@dataclass(frozen=True)
class Proposal:
    id: str
    kind: str
    summary: str
    payload: dict
    created_at: datetime
    expires_at: datetime
    claimed_at: datetime | None
    outcome: dict | None

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


class ProposalStore:
    """SQLite-backed. The file is small and local; operations are a single statement."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        if self._path.parent != Path():
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self._path, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def create(
        self,
        *,
        kind: str,
        summary: str,
        payload: dict,
        ttl: timedelta = DEFAULT_TTL,
        now: datetime | None = None,
    ) -> Proposal:
        """Record a proposal and return it with the id an execution will need."""
        created = now or datetime.now(UTC)
        proposal = Proposal(
            id=uuid.uuid4().hex,
            kind=kind,
            summary=summary,
            payload=payload,
            created_at=created,
            expires_at=created + ttl,
            claimed_at=None,
            outcome=None,
        )

        self._db.execute(
            "INSERT INTO proposals (id, kind, summary, payload, created_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                proposal.id,
                proposal.kind,
                proposal.summary,
                json.dumps(proposal.payload),
                proposal.created_at.isoformat(),
                proposal.expires_at.isoformat(),
            ),
        )
        logger.info("Recorded %s proposal %s", kind, proposal.id)
        return proposal

    def get(self, proposal_id: str) -> Proposal | None:
        row = self._db.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        return _row_to_proposal(row) if row else None

    def claim(
        self, proposal_id: str, *, kind: str | None = None, now: datetime | None = None
    ) -> Proposal:
        """Take exclusive ownership of a proposal so it can be executed.

        Raises rather than returning None, because every failure here means the execution
        must not happen and the caller needs to know which reason to report.
        """
        moment = now or datetime.now(UTC)

        proposal = self.get(proposal_id)
        if proposal is None:
            raise ProposalError(f"No proposal with id {proposal_id!r}")
        if kind is not None and proposal.kind != kind:
            raise ProposalError(
                f"Proposal {proposal_id} is a {proposal.kind} proposal, not a {kind} one"
            )
        if proposal.claimed_at is not None:
            raise ProposalError(
                f"Proposal {proposal_id} was already executed at {proposal.claimed_at.isoformat()}"
            )
        if proposal.is_expired(moment):
            raise ProposalError(
                f"Proposal {proposal_id} expired at {proposal.expires_at.isoformat()}"
            )

        # The check above is advisory; this UPDATE is what actually decides. Only one
        # caller can move claimed_at from NULL, so a repeated execution loses here rather
        # than applying the same move twice.
        cursor = self._db.execute(
            "UPDATE proposals SET claimed_at = ? WHERE id = ? AND claimed_at IS NULL",
            (moment.isoformat(), proposal_id),
        )
        if cursor.rowcount != 1:
            raise ProposalError(f"Proposal {proposal_id} was already executed")

        logger.info("Claimed proposal %s", proposal_id)
        return Proposal(
            id=proposal.id,
            kind=proposal.kind,
            summary=proposal.summary,
            payload=proposal.payload,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
            claimed_at=moment,
            outcome=None,
        )

    def record_outcome(self, proposal_id: str, outcome: dict) -> None:
        """Store what actually happened. This is the audit trail, so it is never edited."""
        self._db.execute(
            "UPDATE proposals SET outcome = ? WHERE id = ?",
            (json.dumps(outcome), proposal_id),
        )

    def pending(self, *, now: datetime | None = None) -> list[Proposal]:
        """Proposals still awaiting execution, newest first."""
        moment = (now or datetime.now(UTC)).isoformat()
        rows = self._db.execute(
            "SELECT * FROM proposals WHERE claimed_at IS NULL AND expires_at > ?"
            " ORDER BY created_at DESC",
            (moment,),
        ).fetchall()
        return [_row_to_proposal(row) for row in rows]

    def purge(self, *, before: datetime) -> int:
        """Drop expired proposals that were never executed. Executed ones are kept."""
        cursor = self._db.execute(
            "DELETE FROM proposals WHERE claimed_at IS NULL AND expires_at < ?",
            (before.isoformat(),),
        )
        return cursor.rowcount


def _row_to_proposal(row: sqlite3.Row) -> Proposal:
    return Proposal(
        id=row["id"],
        kind=row["kind"],
        summary=row["summary"],
        payload=json.loads(row["payload"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        claimed_at=datetime.fromisoformat(row["claimed_at"]) if row["claimed_at"] else None,
        outcome=json.loads(row["outcome"]) if row["outcome"] else None,
    )
