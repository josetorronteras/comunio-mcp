# CLAUDE.md

Working guide for Claude Code in this repository.

## What this project is

An **MCP** (Model Context Protocol) server for operating on **Comunio**, the online football
fantasy manager. It exposes a league's squad, market and lineup to the agent, and lets it propose
and — only after human approval — execute moves.

## Guiding principles

Two decisions shape everything else. Both are argued in full in
[`docs/architecture.md`](docs/architecture.md) — read it before changing anything they touch.

**The server calculates, the host agent judges.** There is no LLM inside this project. Deterministic
work (budget arithmetic, formation validation, metrics, optimisation) belongs in the server, where
it is testable; soft judgement belongs to the agent, which already has a model and the conversation.
`propose_*` tools are deterministic optimisers, not model calls.

**Approval in cascade.** Tools are model-controlled, so nothing in the protocol stops a model from
calling `execute_bid`. Three mechanisms are stacked: the host's own approval dialog (free, relied on
for nothing), `execute_*` accepting only a `proposal_id` issued by the matching `propose_*`, and
`elicitation` confirmation showing the real figures where the client supports it. **Nothing that
spends money, changes the lineup or touches the market runs without a proposal the user has seen.**

Tool layers:

| Layer | Examples | Contract |
| --- | --- | --- |
| **Read** | `get_squad`, `get_market`, `get_lineup_deadline` | Query only. Never mutates. |
| **Propose** | `propose_lineup`, `propose_bid` | Deterministic. Persists a proposal, returns it with a `proposal_id`. Never calls a write endpoint. |
| **Execute** | `execute_lineup`, `execute_bid` | Takes a `proposal_id`. Applies a stored proposal. Decides nothing. |

A `propose_*` tool never chains internally into its `execute_*` counterpart. When it is unclear
which layer a new tool belongs to, ask before implementing it.

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
- Never commit Comunio credentials. They live in `.env`, which is git-ignored.

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

Planned, created as each part is implemented — link them here and from `README.md` when they land:

| Document | Contents |
| --- | --- |
| `docs/tools.md` | MCP tool catalogue: parameters, response, layer and effects |
| `docs/comunio-api.md` | Comunio endpoints used, authentication, formats, quirks and limits |

Criteria:

- `README.md` is the entry point (what it is, quick start, links to `docs/`). Detail lives in
  `docs/`, not in the README.
- Every MCP tool is documented in `docs/tools.md` **in the same change** that implements it.
- Tool descriptions in code are what the model reads: they must be precise and state explicitly
  whether the tool mutates state.
- Document the *why* behind non-obvious decisions, not the *what* (the code already says that).
- All documentation in English, like this file.