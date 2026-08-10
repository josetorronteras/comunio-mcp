# Architecture

Design decisions for the Comunio MCP server. Each decision records *why*, because the reasoning is
what future changes need to argue against.

Protocol background lives in [mcp-protocol.md](mcp-protocol.md); this document assumes it.

---

## Decision 1 — The server calculates, the host agent judges

**Status:** accepted, 2026-08-08.

### Context

MCP's `sampling` primitive — a server asking the host's LLM to reason on its behalf — is
**deprecated** as of protocol version `2026-07-28`. The only remaining way for the server itself to
"reason" would be to embed an LLM SDK, which means a second API key, paying for tokens twice, and a
model reasoning without any of the user's conversational context.

### Decision

**The server contains no LLM.** It is a plain Python process. Judgement stays in the host agent
(Claude Desktop, Claude Code, …), which already has a model and already has the conversation.

This is not the same as making the server dumb. Everything deterministic belongs in the server,
where it is testable:

- Budget arithmetic — how much can be bid without going broke.
- Formation validation — a 4-3-3 has four defenders, not five.
- Metrics — expected points, averages, form, price per point.
- Availability — suspended and injured players cannot be fielded.
- Optimisation — given a scoring criterion, the XI that maximises expected points.

What the agent adds on top is the soft judgement: *"Lewandowski has blanked three weeks running but
he is playing the bottom club, I would keep him."*

### Consequences

- `propose_*` tools are **deterministic optimisers**, not LLM calls. They return a candidate move
  *and the metrics that justify it*, so the agent can argue with the result.
- Read tools return structured, metric-rich data rather than prose — the agent does the narrating.
- No LLM API key, no GPU, no inference cost anywhere in this project.
- The interesting logic is unit-testable without mocking a model.

---

## Decision 2 — Approval in cascade

**Status:** accepted, 2026-08-08. One sub-policy still open (see below).

### Context

MCP tools are **model-controlled**: the LLM decides on its own when to call them. Nothing in the
protocol stops a model from invoking `execute_bid`. Three mechanisms could stand between that
decision and real money being spent, and none is sufficient alone:

| Mechanism | Strength | Weakness |
| --- | --- | --- |
| Host approval dialog | Free, works everywhere | Generic, often shows raw JSON, behaviour varies per client, and one "always allow" disables it forever. Not under our control. |
| `elicitation` | Shows the real operation, enforced by us, cannot be permanently bypassed | Requires the client to declare the `elicitation` capability |
| `propose` / `execute` split | Works in any client | Worthless on its own: the model can call `execute_*` directly and skip the proposal |

### Decision

Use **all three, stacked**:

1. **The host dialog** comes for free on top of everything. We rely on it for nothing.
2. **`execute_*` tools only accept a `proposal_id`** issued by the matching `propose_*` tool. An
   execution cannot exist without a proposal the user has seen. `execute_*` never re-decides
   anything: it applies a stored, validated proposal.
3. **`execute_*` asks for confirmation via `elicitation`** when the client supports it, showing the
   real figures ("Bid €4,500,000 for Vinicius Jr. You would have €1.2M left. Confirm?").

Since MCP is stateless as of `2026-07-28`, proposals cannot live in connection memory. They are
**persisted** with an expiry, which also gives us an audit trail: what was proposed, when, with what
numbers, and whether it was executed.

### Open sub-policy

What `execute_*` does when the client does **not** support `elicitation`: refuse outright, or fall
back to the `proposal_id` check plus the host dialog. To be decided — it needs checking which
clients actually implement `elicitation` against spec `2026-07-28`.

### What the write API forces on top

The market write endpoints have now been captured and verified (see
[comunio-api.md](comunio-api.md)). Three of their properties constrain the execute layer
before a line of it is written:

- **Accepting an offer is instant and irreversible** (`processImmediately: true`), while a
  bid is queued until the transfer round and can be withdrawn. The confirmation before an
  accept therefore has to be stronger than the one before a bid — there is nothing to undo
  it with.
- **Responses carry a per-item status inside an outer one.** An outer `OK` with a failed
  item inside is possible, so an `execute_*` must report what each item actually did.
  Reporting success from the outer field is how a tool claims to have placed a bid it did
  not place.
- **Writes must never be auto-retried.** The client retries once on a 401, which is safe
  for `GET` and would double-apply a bid.

### Consequences

- Persistence is a hard requirement from day one, not a later optimisation.
- Proposals need an expiry: a lineup proposal is meaningless after the deadline, and a bid is
  meaningless once the market rolls over.
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
- `mcp.server.elicitation` exists, exposing `elicit_with_validation` and `elicit_url`, and
  `Elicit` is available for resolvers. **Decision 2's approval design is supported by the
  SDK.**
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

## Tool layers

Derived from the two decisions above:

| Layer | Examples | Contract |
| --- | --- | --- |
| **Read** | `get_squad`, `get_market`, `get_lineup_deadline` | Query only. Never mutates. Returns structured data plus metrics. |
| **Propose** | `propose_lineup`, `propose_bid` | Deterministic. Computes a candidate, persists it, returns it with a `proposal_id` and the numbers behind it. Touches no write endpoint. |
| **Execute** | `execute_lineup`, `execute_bid` | Takes a `proposal_id`. Confirms via elicitation where available. Applies the stored proposal to Comunio. Decides nothing. |

Rules:

- A `propose_*` tool never chains internally into its `execute_*` counterpart.
- Nothing that spends money, changes the lineup or touches the market runs without a proposal the
  user has seen.
- When it is unclear which layer a new tool belongs to, ask before implementing it.

---

## Still open

- **How to talk to Comunio.** Official API, unofficial API or scraping — the largest remaining
  unknown. Nothing above depends on the answer.
- **Where proposals are stored.** SQLite is the obvious default; not yet decided.
- **Transport.** stdio is the natural fit for a personal server, and it is also what makes
  environment-variable credentials the documented approach. Streamable HTTP would drag in OAuth 2.1.
- **Client support for `elicitation`**, which settles the open sub-policy in Decision 2.
