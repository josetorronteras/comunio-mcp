# Development

Everything runs in Docker. The only thing you need on the host is Docker with
`docker compose`.

## Layout

```
pyproject.toml            project metadata, dependencies, ruff and pytest config
Dockerfile                the single image, used for the server and for dev tasks
docker-compose.yml        dev tasks: server, test, lint
src/comunio_mcp/
├── __init__.py           main(): configures logging and runs the server
├── __main__.py           python -m comunio_mcp
├── metadata.py           server name and version, shared by server and tools
├── config.py             settings read from the environment
├── context.py            the lifespan object every tool reaches through ctx
├── check_auth.py         the auth-check entry point, not part of the server
├── server.py             the MCPServer instance and tool registration
├── comunio/              the Comunio side: client, auth, session, one module per endpoint
└── tools/
    └── squad.py          one module per tool, each exposing register(mcp)
tests/
```

Adding a tool means adding a module under `tools/` with a `register(mcp)` function and
calling it from `server.py`.

## Everyday commands

```bash
docker compose build          # build the image
docker compose run --rm test  # pytest
docker compose run --rm lint  # ruff
```

After changing dependencies in `pyproject.toml`, rebuild. Source changes do not need a
rebuild for `test` and `lint`: `./src` and `./tests` are bind-mounted, and the package is
installed with `pip install --editable`.

## Running the server by hand

The server speaks MCP over **stdio**: it reads JSON-RPC from stdin and writes it to
stdout. Running it without a client just leaves it waiting.

```bash
docker run -i --rm comunio-mcp
```

You can drive it directly, which is the quickest end-to-end check. Every request must
carry the protocol version in `_meta` — as of `2026-07-28` there is no `initialize`
handshake:

```bash
META='"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"smoke","version":"1.0.0"},"io.modelcontextprotocol/clientCapabilities":{}}'

{ printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"get_account\",\"arguments\":{},$META}}"; sleep 3; } \
  | docker run -i --rm comunio-mcp 2>/dev/null
```

The `sleep` matters: without it stdin closes and the process can exit before it has
answered.

Useful methods for poking at the server: `server/discover` (identity, capabilities and
supported protocol versions), `tools/list`, `tools/call`.

## Logging

**Never write to stdout.** It shares the channel with JSON-RPC, so a stray `print()`
corrupts the stream and breaks the server. `main()` configures `logging` to stderr; use
`logging.getLogger(__name__)` in modules, or `ctx.info(...)` inside a tool when you want
the message to reach the client.

Container stderr is visible with `docker compose logs`, or directly when you run the
image in a terminal.

## Notes on the SDK

Details and sources in [mcp-protocol.md](mcp-protocol.md); the practical points:

- The API is `MCPServer` from `mcp.server`. **`mcp.server.fastmcp` does not exist in
  2.0.0** — it was removed, not renamed. Examples written against 1.x will not run.
- **There are two different `Context` classes and only one works in a tool.** Use
  `from mcp.server.mcpserver import Context`. Annotating a tool parameter with
  `mcp.server.context.Context` — the middleware one — fails at import with
  `PydanticInvalidForJsonSchema`, because the SDK does not recognise it and tries to put
  it in the tool's input schema.
- The lifespan object reaches a tool as `ctx.request_context.lifespan_context`.
- Pydantic aliases: use `validation_alias` rather than `alias` to read Comunio's camelCase
  fields. A plain `alias` also changes the *output*, so `structuredContent` would come out
  as a mix of `teamValue` and `budget`.
- Model fields are **snake_case in Python** and serialised to camelCase on the wire:
  `ToolAnnotations(read_only_hint=True)` appears as `"readOnlyHint": true` in
  `tools/list`.
- Tool schemas come from type hints and docstrings. A Pydantic return type becomes the
  `outputSchema` and the response carries `structuredContent`, so `Field(description=...)`
  is documentation the model actually reads.
- The HTTP client bundled with the SDK is **`httpx2`**, not `httpx`.
