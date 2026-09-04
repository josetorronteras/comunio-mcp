# Comunio MCP

[![CI](https://github.com/josetorronteras/comunio-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/josetorronteras/comunio-mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/josetorronteras/comunio-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/josetorronteras/comunio-mcp)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-io.github.josetorronteras%2Fcomunio-blue)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.josetorronteras/comunio)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An **MCP** (Model Context Protocol) server for [Comunio](https://www.comunio.es/es), the online
football fantasy manager.

It gives an AI assistant access to your league — squad, market, offers, standings, transfers — and
lets it act on your behalf: bid, sell, set the lineup. One line, `client ↔ MCP ↔ Comunio`, and this
is the middle segment.

> **Status: in daily use against a real account.** Nineteen tools: reading the squad, market,
> offers, standings and transfers, and acting on the market, bids and lineup. It talks to
> Comunio's **unofficial** API, which can change without notice — see
> [docs/comunio-api.md](docs/comunio-api.md) for what is mapped and what is not.

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

- [Docker](https://docs.docker.com/get-docker/).
- A Comunio account. There is no API key and no sign-up — the server logs in as you.

Nothing else needs to be installed on the host.

## Quick start

The image is published, so there is nothing to clone and nothing to build. Put your
credentials in a file only you can read, rather than in a command your shell will
remember:

```bash
install -m 600 /dev/null ~/.comunio.env
$EDITOR ~/.comunio.env      # COMUNIO_USERNAME=you
                            # COMUNIO_PASSWORD=...

claude mcp add comunio -- docker run -i --rm \
  --env-file "$HOME/.comunio.env" \
  ghcr.io/josetorronteras/comunio-mcp
```

Then ask your assistant how your team is doing — `get_account` is the quickest proof that
the credentials work.

For Claude Desktop, for the `uvx` route that skips Docker entirely, and for what each
variable does, see [docs/setup.md](docs/setup.md).

## Documentation

- [Setup](docs/setup.md) — running the image and connecting it to an MCP client
- [Tools](docs/tools.md) — what each tool returns and what it touches
- [Development](docs/development.md) — layout, dev commands, SDK gotchas
- [Architecture](docs/architecture.md) — design decisions and the reasoning behind them
- [Comunio API](docs/comunio-api.md) — authentication, the link index and what is still unmapped
- [MCP protocol notes](docs/mcp-protocol.md) — the parts of MCP `2026-07-28` that shape this project
- [Changelog](CHANGELOG.md) — what changed in each release

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers the setup,
what belongs in the server and what does not, and the rules that are not negotiable — no
credentials, no tokens and no real account data in a commit. Vulnerabilities go through
[SECURITY.md](SECURITY.md) rather than a public issue.

## Versioning

Releases follow [semantic versioning](https://semver.org/), and what it covers is **the MCP
surface**: tool names, their input schemas, and the fields their responses carry. Renaming a
tool, dropping a parameter or removing a field from a response is a major version. Adding a
tool, an optional parameter or a field is a minor one.

What it cannot cover is Comunio. This talks to an unofficial API that can change or break
without notice, and no version number here can promise otherwise. When it does change, the
fix ships as a patch or a minor — the tools stay the same shape.

## License

[MIT](LICENSE).

## Disclaimer

Unofficial project, not affiliated with Comunio. Use it with your own account and at your own risk.
