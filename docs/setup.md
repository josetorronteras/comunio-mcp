# Setup

## Requirements

Docker with `docker compose`. Nothing else needs to be installed on the host — no Python,
no package manager. (An alternative path without Docker, for hosts that already run
`uv`, is covered under [Without Docker](#without-docker-uvx) below.)

## Build

```bash
git clone https://github.com/josetorronteras/comunio-mcp.git
cd comunio-mcp
docker compose build
```

That produces the `comunio-mcp` image.

## Connecting it to an MCP client

The server uses the **stdio** transport, so the client launches the container itself and
talks to it over stdin/stdout. Compose is not involved — it only exists for development
tasks.

### Claude Code

```bash
claude mcp add comunio -- docker run -i --rm comunio-mcp
```

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (create it if it
is not there) and restart the app:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "comunio-mcp"]
    }
  }
}
```

`-i` is required — without it the container gets no stdin and the client sees a server
that never answers. `--rm` keeps a container from piling up on every launch.

### Without Docker (`uvx`)

The package is a regular pip-installable Python project (see `pyproject.toml`), so any
host with [`uv`](https://docs.astral.sh/uv/) installed can run it straight from the git
repository, without building the image and without a local clone:

```bash
uvx --from git+https://github.com/josetorronteras/comunio-mcp@<commit-sha> comunio-mcp
```

Pin `<commit-sha>` to an exact commit rather than `@main` — there is no compatibility
guarantee between commits yet, and an unpinned ref can change under you on every restart.

#### Claude Code

```bash
claude mcp add comunio -- uvx --from git+https://github.com/josetorronteras/comunio-mcp@<commit-sha> comunio-mcp
```

#### Claude Desktop

```json
{
  "mcpServers": {
    "comunio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/josetorronteras/comunio-mcp@<commit-sha>",
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
cp .env.example .env    # fill it in
docker compose run --rm auth-check
```

It logs in, refreshes, and reports how long the token lasts. It prints no token.

### Passing them to the client

```bash
claude mcp add comunio -- docker run -i --rm \
  -e COMUNIO_USERNAME=you \
  -e COMUNIO_PASSWORD=secret \
  comunio-mcp
```

For Claude Desktop, add them to the `args` array the same way, or use `--env-file` with a
path to your `.env`:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--env-file", "/absolute/path/to/.env", "comunio-mcp"]
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
  -- uvx --from git+https://github.com/josetorronteras/comunio-mcp@<commit-sha> comunio-mcp
```

Claude Desktop, via `env`:

```json
{
  "mcpServers": {
    "comunio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/josetorronteras/comunio-mcp@<commit-sha>",
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
