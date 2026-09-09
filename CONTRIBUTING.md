# Contributing

Thanks for looking. This is a small project with a narrow scope, and the scope is the
part worth reading before you write code.

## What belongs here

The server is an **adapter**. It makes Comunio's unofficial API callable and its answers
legible, and that is all. Two rules follow, both argued in full in
[docs/architecture.md](docs/architecture.md):

- **No strategy, no optimiser.** Which player to buy, which XI is best, whether a price is
  worth paying — that is the assistant's job, not the server's. There is no LLM inside
  this project and there is not meant to be one.
- **No confirmation ceremony.** A write tool declares what it does through its
  annotations and description, then does it. Asking the user first happens in the client,
  which has the conversation. No `propose_*`/`execute_*` split, no proposal ids.

The MCP server is the whole deliverable: no skills, no prompt packs, no companion CLI.
If a behaviour only works because a client was primed with extra instructions, it does
not belong here.

## Setting up

Everything runs in Docker; nothing else needs installing on the host.

```bash
git clone https://github.com/josetorronteras/comunio-mcp.git
cd comunio-mcp
docker compose build
docker compose run --rm test   # pytest
docker compose run --rm lint   # ruff
```

Layout, the SDK gotchas that bite newcomers, and how to drive the server by hand are in
[docs/development.md](docs/development.md).

## Adding a tool

1. A module under `src/comunio_mcp/tools/` exposing `register(mcp)`.
2. Registered from `server.py`.
3. Named `get_*` **only** if it never mutates — the server's `instructions` tell hosts to
   trust that prefix, so a mutating `get_*` breaks every client at once.
4. Annotations and description state the effects explicitly. Tool schemas are generated
   from type hints and docstrings, so both are load-bearing code.
5. Models are **allowlists**: declare only the fields worth exposing. Raw Comunio
   responses carry email addresses and invitation codes that must never reach a model's
   context.
6. Documented in [docs/tools.md](docs/tools.md) **in the same pull request**. A behaviour
   change without its documentation is incomplete.
7. Covered by tests. A write tool's guards run *before* anything is sent, and are tested
   by asserting no request left the process — not by the wording of the error.

## Pull requests

- One pull request is one coherent change a reviewer can read in a single sitting.
  Refactors travel separately from behaviour changes; prefer stacking small PRs.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- CI must be green: tests, ruff, the secret scan and the `server.json` metadata check.

## Never in a commit

- **Credentials.** They live in `.env`, which is git-ignored. `.env.example` documents the
  variables with empty values.
- **Tokens**, in output, error messages or logs. A failed login can echo credentials back
  in its body, so only the HTTP status is safe to surface.
- **Real account data**, in fixtures, docs, commits or PRs. When a real API response is
  used as a reference, copy the *shape* and invent every value — ids, league names and
  amounts identify a real account, and git history does not forget.

## Reporting a problem

Bugs and ideas go to [Issues](https://github.com/josetorronteras/comunio-mcp/issues); the
templates ask for what is needed. Security issues go through
[SECURITY.md](SECURITY.md) instead, not a public issue.

When Comunio changes its API — which it can, without notice — an issue that shows the
request and the new response shape (with invented values) is the most useful thing you can
file.
