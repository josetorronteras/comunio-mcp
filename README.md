# Comunio MCP

An **MCP** (Model Context Protocol) server for [Comunio](https://www.comunio.es/es), the online
football fantasy manager.

It gives an AI agent read access to your league — squad, market, lineup deadline — and lets it
reason about moves. Anything that changes your team is split into a *proposal* the agent produces
and an *execution* step that only runs after you approve it.

> **Status: early development.** Eighteen tools: reading the squad, market, offers, standings and
> transfers, and acting on the market, bids and lineup. All verified against a real account.

## How it works

Tools come in three layers, and the boundary between them is deliberate:

| Layer | Examples | What it does |
| --- | --- | --- |
| **Read** | `get_squad`, `get_market`, `get_lineup_deadline` | Query only. Never changes anything. |
| **Propose** | `propose_lineup`, `propose_bid` | Works out a candidate move and hands it back with the numbers behind it. Nothing is sent to Comunio. |
| **Execute** | `execute_lineup`, `execute_bid` | Applies a proposal you have already seen. |

Two properties fall out of that:

**There is no AI model inside this server.** It does the arithmetic — budgets, formations, expected
points, who is suspended — and leaves the judgement to the assistant you are already talking to. No
API key, no GPU, no inference cost.

**Nothing runs without your approval.** An execution can only apply a proposal that was generated
first, and it asks you to confirm the real figures before it acts. The agent cannot go straight from
"I think you should bid" to bidding.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with `docker compose`.

Everything runs in containers — nothing else needs to be installed on the host.

## Quick start

```bash
docker compose build
claude mcp add comunio -- docker run -i --rm comunio-mcp
```

Then ask your assistant how your team is doing. Full instructions, including Claude Desktop, are in
[docs/setup.md](docs/setup.md).

## Documentation

- [Setup](docs/setup.md) — building the image and connecting it to an MCP client
- [Tools](docs/tools.md) — what each tool returns and what it touches
- [Development](docs/development.md) — layout, dev commands, SDK gotchas
- [Architecture](docs/architecture.md) — design decisions and the reasoning behind them
- [Comunio API](docs/comunio-api.md) — authentication, the link index and what is still unmapped
- [MCP protocol notes](docs/mcp-protocol.md) — the parts of MCP `2026-07-28` that shape this project

Contributor conventions are in [CLAUDE.md](CLAUDE.md).

## Disclaimer

Unofficial project, not affiliated with Comunio. Use it with your own account and at your own risk.
