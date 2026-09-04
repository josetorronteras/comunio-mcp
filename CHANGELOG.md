# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

What the version number covers is **the MCP surface**: tool names, their input schemas and
the fields their responses carry. Renaming a tool, dropping a parameter or removing a
response field is a major version; adding a tool, an optional parameter or a field is a
minor one. It cannot cover Comunio's unofficial API, which can change without notice —
when it does, the fix ships as a patch or a minor and the tools keep their shape.

## [1.0.2] — unreleased

### Added

- Published Docker image at `ghcr.io/josetorronteras/comunio-mcp`, built for `amd64` and
  `arm64` on every release tag. Running the server no longer needs a clone and a local
  build.
- `server.json`, and a release workflow that lists the server in the
  [MCP Registry](https://registry.modelcontextprotocol.io) under
  `io.github.josetorronteras/comunio`.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md` and this changelog.
- A CI check that `server.json`, `pyproject.toml` and the Dockerfile's ownership label
  cannot drift apart.

### Fixed

- The version in `pyproject.toml`, which stayed at `1.0.0` through the `v1.0.1` tag, so
  the server reported a version it was not.
- Test collection on hosts where the bind-mounted `./tests` made pytest resolve
  `tests.conftest` twice and refuse to run anything.

## [1.0.1] — 2026-08-24

### Fixed

- A null figure under `period=live` no longer breaks `get_standings`.

## [1.0.0] — 2026-08-22

First release. Nineteen tools over Comunio's unofficial API, in daily use against a real
account.

### Added

- **Reads:** account, squad, player, standings, market, offers, transfers, news and
  watchlist.
- **Writes:** list on market, unlist, change listing price, place bid, change bid,
  withdraw bid, accept offer and set lineup.
- Docker-first setup, plus a `uvx`-from-git route for hosts that already run `uv`.
- Documentation of the architecture, the MCP protocol notes, the Comunio API mapping and
  the tool catalogue.

[1.0.2]: https://github.com/josetorronteras/comunio-mcp/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/josetorronteras/comunio-mcp/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/josetorronteras/comunio-mcp/releases/tag/v1.0.0
