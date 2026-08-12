# Comunio MCP

An **MCP** (Model Context Protocol) server for [Comunio](https://www.comunio.es/es), the online
football fantasy manager.

It gives an AI assistant access to your league — squad, market, offers, standings, transfers — and
lets it act on your behalf: bid, sell, set the lineup. One line, `client ↔ MCP ↔ Comunio`, and this
is the middle segment.

> **Status: early development.** Eighteen tools: reading the squad, market, offers, standings and
> transfers, and acting on the market, bids and lineup. All verified against a real account.

## How it works

Tools come in two kinds, and the name tells you which:

| Kind | Naming | What it does |
| --- | --- | --- |
| **Read** | `get_squad`, `get_market`, `get_offers` | Query only. Never changes anything. Always safe. |
| **Write** | `place_bid`, `accept_offer`, `set_lineup` | Changes your team or spends your money. |

Two properties fall out of that:

**There is no AI model inside this server, and no strategy either.** It translates: it makes
Comunio's API callable and its answers legible — unpicking slot numbers, the five different ways one
endpoint writes "no data", a ranking field that is `0` for every row. Which player to buy is left to
the assistant you are already talking to. No API key, no GPU, no inference cost.

**Your client asks before it acts.** Every mutating tool declares itself as one, so your MCP client
knows to stop and ask you first. The server does not second-guess a move once you have agreed to it,
and it reports what Comunio actually answered rather than assuming it worked.

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
