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

None yet — no tool talks to Comunio so far. When they do, credentials will be passed as
environment variables (the documented approach for stdio servers) and the client
configuration will need `-e` flags. They never go in the image or in git.
