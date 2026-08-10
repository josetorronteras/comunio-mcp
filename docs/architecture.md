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

### Consequences

- Persistence is a hard requirement from day one, not a later optimisation.
- Proposals need an expiry: a lineup proposal is meaningless after the deadline, and a bid is
  meaningless once the market rolls over.
- Every tool must state in its description whether it mutates state — that description is what the
  model reads.

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
