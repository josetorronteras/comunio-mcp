# Setup

## Requirements

Docker. Nothing else needs to be installed on the host — no Python, no package manager,
and no clone of this repository. (An alternative path without Docker, for hosts that
already run `uv`, is covered under [Without Docker](#without-docker-uvx) below.)

## The image

Releases are published to the GitHub Container Registry:

```
ghcr.io/josetorronteras/comunio-mcp:latest    # the current release
ghcr.io/josetorronteras/comunio-mcp:1.0.2     # a specific one
```

Built for `linux/amd64` and `linux/arm64`, so it runs natively on Apple Silicon.

Pin a version tag rather than `latest` if you want your client's tools to keep the shape
it saw; `latest` moves on every release. Docker caches the image on first run, so there is
nothing to build and nothing to pull by hand.

Building it yourself is only needed for development — see
[development.md](development.md).

## Connecting it to an MCP client

The server uses the **stdio** transport, so the client launches the container itself and
talks to it over stdin/stdout.

### Claude Code

```bash
claude mcp add comunio -- docker run -i --rm \
  -e COMUNIO_USERNAME=you -e COMUNIO_PASSWORD=secret \
  ghcr.io/josetorronteras/comunio-mcp
```

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (create it if it
is not there) and restart the app:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "COMUNIO_USERNAME",
        "-e", "COMUNIO_PASSWORD",
        "ghcr.io/josetorronteras/comunio-mcp"
      ],
      "env": {
        "COMUNIO_USERNAME": "you",
        "COMUNIO_PASSWORD": "secret"
      }
    }
  }
}
```

`-e VAR` without a value forwards the variable the client already set, which keeps the
password in one place in the file rather than two.

`-i` is required — without it the container gets no stdin and the client sees a server
that never answers. `--rm` keeps a container from piling up on every launch.

### A client that reads the MCP Registry

The server is listed as **`io.github.josetorronteras/comunio`**. A client that installs
from the registry finds the image and the environment variables it needs there, so the
only thing left to supply is your account.

### Without Docker (`uvx`)

The package is a regular pip-installable Python project (see `pyproject.toml`), so any
host with [`uv`](https://docs.astral.sh/uv/) installed can run it straight from the git
repository, without building the image and without a local clone:

```bash
uvx --from git+https://github.com/josetorronteras/comunio-mcp@v1.0.2 comunio-mcp
```

Pin a **release tag** rather than `@main`: an unpinned ref changes under you on every
restart, and a tag is the only ref that promises the tools will keep the shape your client
saw. A commit SHA works too and is what a gateway manifest usually wants.

#### Claude Code

```bash
claude mcp add comunio -- uvx --from git+https://github.com/josetorronteras/comunio-mcp@v1.0.2 comunio-mcp
```

#### Claude Desktop

```json
{
  "mcpServers": {
    "comunio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/josetorronteras/comunio-mcp@v1.0.2",
        "comunio-mcp"
      ]
    }
  }
}
```

This is also the route MCP gateways that spawn stdio servers directly use instead of
running each one in its own container — for example
[MCPJungle](https://github.com/mcpjungle/mcpjungle).

## Checking it works

Ask the client to call `get_account`. It answers with the manager's budget, squad totals
and league rules — which also proves the credentials work, since it is a real Comunio
call.

To check without a client at all, see the direct JSON-RPC recipe in
[development.md](development.md).

## Credentials

Your Comunio account is passed to the container as environment variables — the documented
approach for stdio servers. They never go in the image or in git.

| Variable | Required | Default |
| --- | --- | --- |
| `COMUNIO_USERNAME` | yes | — |
| `COMUNIO_PASSWORD` | yes | — |
| `COMUNIO_TIMEZONE` | no | `Europe/Madrid` |
| `COMUNIO_USER_AGENT` | no | the captured browser user agent |

Without them the server still starts and lists its tools; every tool then fails with a
message saying which variables are missing.

To check the credentials work before wiring anything up:

```bash
cp .env.example .env    # fill it in, from a clone of the repository
docker compose run --rm auth-check
```

It logs in, refreshes, and reports how long the token lasts. It prints no token.

### Passing them to the client

```bash
claude mcp add comunio -- docker run -i --rm \
  -e COMUNIO_USERNAME=you \
  -e COMUNIO_PASSWORD=secret \
  ghcr.io/josetorronteras/comunio-mcp
```

For Claude Desktop, add them to the `args` array the same way, or use `--env-file` with a
path to your `.env`:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/absolute/path/to/.env",
        "ghcr.io/josetorronteras/comunio-mcp"
      ]
    }
  }
}
```

The `--env-file` form keeps the password out of the config file. Details of the
authentication flow are in [comunio-api.md](comunio-api.md).

For the `uvx` route, the client sets them the same way it sets any environment variable
for a process it spawns. Claude Code:

```bash
claude mcp add comunio -e COMUNIO_USERNAME=you -e COMUNIO_PASSWORD=secret \
  -- uvx --from git+https://github.com/josetorronteras/comunio-mcp@v1.0.2 comunio-mcp
```

Claude Desktop, via `env`:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/josetorronteras/comunio-mcp@v1.0.2",
        "comunio-mcp"
      ],
      "env": {
        "COMUNIO_USERNAME": "you",
        "COMUNIO_PASSWORD": "secret"
      }
    }
  }
}
```

An MCP gateway that registers this server via a manifest (rather than a per-client
config) passes the same variables through its own `env` block instead.
