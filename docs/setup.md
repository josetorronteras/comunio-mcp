# Setup

## Requirements

Docker with `docker compose`. Nothing else needs to be installed on the host — no Python,
no package manager.

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

## Checking it works

Ask the client to call the `ping` tool. It answers with the server name, its version and
the current UTC time, and touches nothing in Comunio.

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
| `COMUNIO_USER_AGENT` | no | `comunio-mcp/0.1.0` |

Without them the server still starts and `ping` still works; only the tools that reach
Comunio fail, with a message saying what is missing.

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
