# CLAUDE.md

Working guide for Claude Code in this repository.

## What this project is

An **MCP** (Model Context Protocol) server for operating on **Comunio**, the online football
fantasy manager. It exposes a league's squad, market and lineup to the agent, and lets it propose
and — only after human approval — execute moves.

**The MCP server is the whole deliverable.** No agent skills, no prompt packs, no companion CLI, no
client-side helpers. Anything a user should be able to do lives in a tool, documented in
[`docs/tools.md`](docs/tools.md); if a behaviour only works because a particular client was primed
with extra instructions, it does not belong here. Documentation describes the server and nothing
else.

## Guiding principles

Two decisions shape everything else. Both are argued in full in
[`docs/architecture.md`](docs/architecture.md) — read it before changing anything they touch.

**The server translates, it does not decide.** There is no LLM inside this project and no strategy
either. The test for anything the server computes is: *could the client build a correct request, or
read the answer correctly, without this?* If no — slot numbers, Comunio's five ways of writing "no
data", a `position` field that is `0` for everyone, seller id `1`, allowlisting the fields that
carry other people's email addresses — it is adapter work and belongs here. If yes — which XI is
best, whether a price is worth paying — it belongs to the client. **There is no optimiser and there
is not meant to be one.**

**Approval belongs to the host.** The server declares what a tool does through its annotations and
its description, and then does it. It runs no confirmation ceremony: no `propose_*`/`execute_*`
split, no `proposal_id`, no persisted proposals, no `elicitation`. Confirming with the user happens
in the client, which has the conversation. What the server still owes: refusing calls that are
**wrong** — `game:offer:withdraw` and `game:offer:decline` share a path, so an unchecked id
*declines* somebody else's offer instead of withdrawing a bid — and reporting what Comunio actually
answered instead of assuming success.

Tool kinds:

| Kind | Naming | Contract |
| --- | --- | --- |
| **Read** | `get_*` | Query only. Never mutates. `read_only_hint=True`. |
| **Write** | anything else | Mutates. Effects declared in the annotations and stated in the description. Validates the call, sends one operation, reports the result. |

`get_` is a promise the server's `instructions` tell the host to trust, so a mutating `get_*` breaks
every client at once. A write tool sends one operation and does not chain. Refuse malformed and
misdirected calls, never merely unwise ones, and never invent a rule Comunio does not have.

## Git conventions

- **Never add Claude Code as a commit co-author.** No `Co-Authored-By: Claude ...` trailers.
- **Never mention Claude or Claude Code in pull request descriptions.** No "Generated with..."
  footer.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).
- **Small pull requests, always.** One PR = one coherent change that a reviewer can read in a single
  sitting. If a task grows, split it into several PRs rather than letting one grow.
  - Prefer stacking sequential PRs over a single large one.
  - Refactors travel in their own PR, separate from behaviour changes.
- Do not commit or push unless the user asks for it.
- Never commit Comunio credentials. They live in `.env`, which is git-ignored; `.env.example`
  documents the variables with empty values.
- **Never log or return a token.** Not in tool output, not in error messages, not in debug logs.
  A failed login can echo the credentials back in its body, so only the HTTP status is safe to
  surface.

## Docker first

Whenever possible, **everything runs in Docker**. The goal is that a clone of the repo needs nothing
installed on the host beyond Docker itself.

- Development, tests and the server itself run inside containers, orchestrated with
  `docker compose`.
- Do not assume a runtime, package manager or database is installed on the host machine.
- Any command documented in the docs must be runnable through Docker.
- Dependency and runtime versions are pinned in the images, not left to whatever the host has.
- If something genuinely cannot run in a container, document why in `docs/development.md`.

## Stack

Python 3.12 on MCP protocol version **`2026-07-28`**, SDK `mcp[cli]>=2.0.0,<3.0.0`, everything in
Docker. Rationale in [`docs/architecture.md`](docs/architecture.md) (Decision 3), practical notes in
[`docs/development.md`](docs/development.md). Things that trip people up:

- The entry class is `MCPServer` (`from mcp.server import MCPServer`). **`mcp.server.fastmcp` does
  not exist in 2.0.0** — it was removed, not renamed. Most examples online are 1.x and will not run;
  check the import path before trusting a snippet.
- Model fields are **snake_case in Python**, camelCase on the wire:
  `ToolAnnotations(read_only_hint=True)` serialises as `"readOnlyHint": true`.
- The HTTP client bundled with the SDK is **`httpx2`**, not `httpx`.
- **Never write to stdout** in a stdio server: `print()` corrupts the JSON-RPC stream. Use
  `logging.getLogger(__name__)`, which writes to stderr. MCP's own logging primitive is deprecated.
- Tool schemas are generated from **type hints and docstrings**, so both are load-bearing code, not
  decoration.
- Tools live one module per resource under `src/comunio_mcp/tools/`, each exposing `register(mcp)`,
  called from `server.py`.
- A tool that needs Comunio takes `ctx: Context` from **`mcp.server.mcpserver`** (not
  `mcp.server.context`, which fails at import) and reaches the app through
  `ctx.request_context.lifespan_context`.
- **No path is hardcoded.** Routes come from the `_links` index via `session.link("game:squad")`.
- **Never auto-retry a write.** The 401 retry in `ComunioClient` is safe for `GET` only; retrying a
  `POST` or `PUT` would place a bid twice.
- **A write tool's guards run before anything is sent, and are tested by asserting no request left
  the process** — not by the wording of the error. A guard that only fires after the call is not a
  guard.
- **Models are allowlists.** Declare only the fields worth exposing; the raw responses carry
  email, invitation codes and other data that must never reach the model's context.

## Documentation

Documentation is part of the deliverable, not an extra. **A behaviour change without its
documentation is incomplete.**

Written so far:

| Document | Contents |
| --- | --- |
| [`docs/architecture.md`](docs/architecture.md) | Design decisions and the reasoning behind them |
| [`docs/mcp-protocol.md`](docs/mcp-protocol.md) | MCP `2026-07-28` notes filtered by what affects this project |
| [`docs/setup.md`](docs/setup.md) | Building the image and connecting it to an MCP client |
| [`docs/development.md`](docs/development.md) | Layout, dev commands, running the server by hand, SDK gotchas |
| [`docs/comunio-api.md`](docs/comunio-api.md) | Comunio endpoints, authentication, headers, quirks and unknowns |
| [`docs/tools.md`](docs/tools.md) | MCP tool catalogue: parameters, response, layer and effects |

Criteria:

- `README.md` is the entry point (what it is, quick start, links to `docs/`). Detail lives in
  `docs/`, not in the README.
- Every MCP tool is documented in `docs/tools.md` **in the same change** that implements it.
- **Never put real account data in fixtures, docs, commits or PRs.** When a real API response is
  used as a reference, copy the *shape* and invent every value. Ids, league names and amounts
  identify a real account, and git history does not forget. Test fixtures define named constants
  (`USER_ID`, `MANAGER_NAME`) so no literal is repeated.
- Tool descriptions in code are what the model reads: they must be precise and state explicitly
  whether the tool mutates state.
- Document the *why* behind non-obvious decisions, not the *what* (the code already says that).
- All documentation in English, like this file.