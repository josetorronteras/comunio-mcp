# Architecture

Design decisions for the Comunio MCP server. Each decision records *why*, because the reasoning is
what future changes need to argue against.

Protocol background lives in [mcp-protocol.md](mcp-protocol.md); this document assumes it.

## Scope

What this repository ships is **one MCP server**, and nothing else. No agent skills, no prompt
packs, no companion CLI, no client-side helpers.

The shape is a single line: **client ↔ MCP ↔ Comunio.** The server is the middle segment and only
the middle segment. Everything that happens before the call — deciding a move is a good one, asking
the user whether to go ahead — happens in the client, which has the model and the conversation.
Everything after it is Comunio's. A skill or a bundled prompt lives in the first segment, tied to
one host and invisible to the next client that connects; it is not this project's to ship.

---

## Decision 1 — The server translates, it does not decide

**Status:** revised 2026-08-12. Supersedes "the server calculates, the host agent judges"
(2026-08-08).

### Context

MCP's `sampling` primitive — a server asking the host's LLM to reason on its behalf — is
**deprecated** as of protocol version `2026-07-28`. The only remaining way for the server itself to
"reason" would be to embed an LLM SDK: a second API key, tokens paid for twice, and a model
reasoning without any of the user's conversational context.

The original decision drew the line at **deterministic vs. soft judgement** and put everything
deterministic in the server — including metrics, scoring and lineup optimisation. That line was
drawn too far out. Optimisation is deterministic *and* still a decision: choosing an XI means
choosing a criterion, and the criterion is the interesting part. A server that picks it has decided
for the user in a way no annotation can express.

### Decision

**The server contains no LLM, and no strategy either.** It is an adapter over Comunio's API: it
makes Comunio callable and its answers legible, and it stops there.

The line is not "is this deterministic?" but:

> **Could the client build a correct request, or read the answer correctly, without this?**

If no, it is adapter work and belongs here:

- **Protocol translation.** Comunio's lineup endpoint takes numbered slots `"1"`–`"11"` and never
  says what a number means. Without `slot_plan()` the endpoint is not callable at all.
- **Normalisation.** One endpoint encodes "no data" five different ways (`points: "-"`,
  `recommendedprice: -1`, `pos: ""`, …). The client should not have to know any of them.
- **Fixing broken fields.** The standings payload sends `position: 0` for every row, so rank is
  derived from the order Comunio returns.
- **Identity resolution.** `is_me`, `is_mine` and an offer's `direction` need the signed-in
  manager's id, which only this server holds.
- **Magic numbers.** Seller id `1` means Comunio itself. That belongs behind `from_computer`.
- **Allowlisting.** Raw responses carry email addresses, invitation codes and other managers'
  account flags. Models declare only what is safe to expose.

If yes, it belongs to the client:

- Which XI is best, and by what criterion.
- Whether a price is worth paying, whether a rival is a threat, when to sell.
- Whether a legal move is a wise one.

### Consequences

- No LLM API key, no GPU, no inference cost anywhere in this project.
- **No optimiser.** There is no "best lineup" tool and there is not meant to be one. The server
  hands over the squad, the fixtures and the scoring history; the client picks.
- Read tools return structured data, not prose and not recommendations.
- Derived fields have to justify themselves against the question above. Some already in the tree do
  so only weakly — see *Still open*.

---

## Decision 2 — Approval in cascade

**Status:** revised 2026-08-12. Supersedes "approval in cascade" (2026-08-08).

### Context

MCP tools are **model-controlled**: the LLM decides on its own when to call them, and nothing in the
protocol stops it from spending money. The original decision answered that inside the server, with a
`propose_*` / `execute_*` split: an execution accepted only a `proposal_id` issued by a matching
proposal, and proposals were persisted in SQLite because MCP is stateless as of `2026-07-28`.

That reasoning had a hole in it. The store existed to **carry state between two tool calls** — but
in a client ↔ MCP ↔ Comunio line, what carries state between two calls is the client. The user reads
the figures in the conversation and answers there. The proposal store was the server rebuilding a
conversation it cannot see, from a frozen summary, and the `proposal_id` was never the protection:
it was glue between two calls that only existed because it was glue.

Meanwhile the eight write tools that were actually built put the guarantee somewhere better — in
each tool, against the real API — and shipped without any of it.

### Decision

**Approval is the host's, and it happens outside this project.** The server publishes what a tool
does and does it. It does not run a confirmation ceremony.

What the server is still responsible for:

1. **Declaring effects.** Every mutating tool is annotated `read_only_hint=False`, and `accept_offer`
   — the only irreversible action — is the only one annotated `destructive_hint=True`. Descriptions
   say in words that the tool spends money or changes the team. Annotations and descriptions are the
   interface the host's approval flow is built on; getting them wrong disarms it.
2. **Refusing calls that are wrong, not calls that are unwise.** A request aimed at the wrong
   operation is a bug the client cannot see. `game:offer:withdraw` and `game:offer:decline` resolve
   to the **same path with the same body**, so an id belonging to somebody else's offer would
   *decline* it instead of withdrawing a bid — two different outcomes from one call. Looking the
   offer up first is the only way that call can be correct.
3. **Reporting what happened.** Never assuming it.

What the server stops doing: refusing a legal move because it judges it a bad one. That is
Decision 1 applied to the write side.

`elicitation` goes with the rest. It is a real MCP capability and it would fit the wire shape, but
confirming with the user is the client's job in this design, not a second place to do it.

### What the write API forces

The market write endpoints are captured and verified in [comunio-api.md](comunio-api.md). Three of
their properties are not negotiable, whatever the approval design:

- **Accepting an offer is instant and irreversible** (`processImmediately: true`), while a bid is
  queued until the transfer round and can be withdrawn. That asymmetry is why `accept_offer` carries
  `destructive_hint=True` alone.
- **Responses carry a per-item status inside an outer one.** An outer `OK` wrapping a failed item is
  a real response. Reporting success from the outer field is how a tool claims to have placed a bid
  it did not place, so `ok` always comes from the per-item status.
- **Writes must never be auto-retried.** `ComunioClient` retries once on a 401, which is safe for
  `GET` and would place a bid twice on a `POST`.

### Consequences

- **No proposal store, no `proposal_id`, no expiry, no audit trail.** `proposals.py` and
  `COMUNIO_STATE_DIR` exist only to serve a design that is gone.
- The server keeps no state between calls at all, which is what a stateless protocol was asking for
  in the first place.
- Every tool must state in its description whether it mutates state — that description is what the
  model reads.

---

## Decision 3 — Python MCP SDK 2.0, verified rather than assumed

**Status:** accepted, 2026-08-10.

### Context

Two candidate lines existed when the skeleton was written:

| | SDK 1.x | SDK 2.0 |
| --- | --- | --- |
| Latest | 1.29.0 | 2.0.0, released 2026-07-28 |
| API | `FastMCP` | `MCPServer` |
| Spec | `2025-11-25` | `2026-07-28` |

1.x is the mature line and what most examples online are written against. 2.0.0 was
thirteen days old, described by its authors as "a major rework of the SDK" for the
`2026-07-28` specification.

### Decision

**SDK 2.0, `mcp[cli]>=2.0.0,<3.0.0`, Python 3.12.** The project is greenfield; adopting an
API that has just been replaced would mean starting in debt.

The decision was checked against the real package inside a container rather than taken
from the documentation:

- `from mcp.server import MCPServer` — works.
- **`mcp.server.fastmcp` is gone.** Not renamed: `ModuleNotFoundError`. The 1.x code style
  simply does not run on 2.0.
- `mcp.server.elicitation` exists, exposing `elicit_with_validation` and `elicit_url`. Recorded
  because it was verified, not because it is used: Decision 2 leaves confirmation to the host.
- The SDK depends on `httpx2`, not `httpx`.
- Model fields are snake_case in Python and camelCase on the wire:
  `ToolAnnotations(read_only_hint=True)` is serialised as `"readOnlyHint": true`.

End-to-end over stdio, the server answers `server/discover`, `tools/list` and `tools/call`
correctly, advertising `"supportedVersions": ["2026-07-28"]`.

### Consequences

- `eduardolosilla-mcp`, the sibling project, is on 1.x with `FastMCP`. Its **structure** is
  worth copying — one module per resource exposing `register(mcp)`, Pydantic models with
  `Field(description=...)`, a shared HTTP client through the lifespan, no swallowing of
  HTTP errors — but its **imports and API calls are not portable**.
- Examples found online are overwhelmingly 1.x. Check the import path before trusting any
  snippet.

### Still unverified

Whether the MCP clients we care about negotiate `2026-07-28` in practice. The server
declares only that version. If a client turns out to speak `2025-11-25` only, this
decision needs revisiting — that is the risk knowingly taken here.

---

## Tool kinds

Two, and the boundary is the tool's name:

| Kind | Naming | Contract |
| --- | --- | --- |
| **Read** | `get_*` | Query only. Never mutates. `read_only_hint=True`. Always safe to call. |
| **Write** | anything else | Changes the manager's team or spends their money. `read_only_hint=False`, effects declared in the annotations and stated in the description. Validates the call, sends it, reports what came back. |

Rules:

- **A read tool never writes, and the name is the promise.** `get_` is what the server's
  `instructions` tell the host to trust; a mutating `get_*` would break every client at once.
- **A write tool sends one operation.** No chaining, no "while I'm here". If two things must happen,
  the client makes two calls and sees both results.
- **Refuse malformed and misdirected calls, not unwise ones.** The test is whether the request could
  reach the wrong endpoint or the wrong player, not whether it is a good idea.
- **Never invent a rule Comunio does not have.** If the game allows it, the tool allows it and lets
  Comunio answer.
- Every tool is documented in [tools.md](tools.md) in the same change that implements it.

---

## Still open

- **How to talk to Comunio.** Official API, unofficial API or scraping — the largest remaining
  unknown. Nothing above depends on the answer.
- **Transport.** stdio is the natural fit for a personal server, and it is also what makes
  environment-variable credentials the documented approach. Streamable HTTP would drag in OAuth 2.1.
- **Removing the proposal store.** `proposals.py`, its tests, the lifespan wiring and
  `COMUNIO_STATE_DIR` are still in the tree, serving nothing. They go in their own change.
- **Whether `place_bid` should refuse a bid on the manager's own listing.** It is the last refusal
  in the tree asserting a rule nobody has measured Comunio to have. It is almost certainly
  harmless — bidding against yourself is not a move — but "almost certainly" is what the other
  three said.
