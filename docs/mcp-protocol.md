# MCP protocol notes

Notes taken from the official MCP documentation for protocol version **`2026-07-28`**, filtered by
what actually affects this project. Source: [modelcontextprotocol.io](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture).

This is a reading summary, not a design decision. Decisions live in `docs/architecture.md` once we
make them.

## 1. The shape of the protocol

- **Participants**: an *MCP host* (the AI application: Claude Code, Claude Desktop, an IDE) creates
  one *MCP client* per *MCP server*. Our project is the **server**.
- **Two layers**: a *data layer* (JSON-RPC 2.0: primitives, capabilities, notifications) and a
  *transport layer* (stdio or Streamable HTTP).
- **Transports**:
  - **stdio** — local process, one client, no network. Simplest and the natural fit for a personal
    Comunio server.
  - **Streamable HTTP** — remote, many clients, HTTP POST + optional SSE, OAuth for auth.

### Statelessness (changed in `2026-07-28`)

There is **no `initialize` handshake any more**. MCP is now stateless: every request carries, in its
`_meta` field, the protocol version, the client capabilities and (normally) the client identity:

```json
"_meta": {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientInfo": { "name": "example-client", "version": "1.0.0" },
  "io.modelcontextprotocol/clientCapabilities": { "elicitation": {} }
}
```

Servers must implement a mandatory **`server/discover`** RPC returning supported versions,
capabilities and identity. Clients *may* call it first, or just fire a request and handle an
`UnsupportedProtocolVersionError`.

Practical consequence for us: **the server cannot rely on per-connection memory.** Anything it
needed to remember between calls would need explicit storage rather than connection state — which
is one reason it remembers nothing between calls. Each tool is a round trip to Comunio and back.
The session with Comunio is a process-lifetime cache, not state a call depends on.

### Versioning

- Format `YYYY-MM-DD`; only bumped on backwards-incompatible changes. Current: `2026-07-28`.
- Negotiated per request via `_meta`, plus the `MCP-Protocol-Version` header over HTTP.
- Older clients speak the handshake-based revisions (`2025-11-25` and earlier); the spec documents a
  backwards-compatibility path.

## 2. Server primitives

| Primitive | Who controls it | Methods |
| --- | --- | --- |
| **Tools** | Model — the LLM decides when to call | `tools/list`, `tools/call` |
| **Resources** | Application — the host decides what to load as context | `resources/list`, `resources/templates/list`, `resources/read` |
| **Prompts** | User — explicitly invoked (e.g. slash commands) | `prompts/list`, `prompts/get` |

- Tool definitions carry `name`, `title`, `description` and a JSON Schema `inputSchema`. The SDK
  generates these from Python type hints and docstrings.
- Resources are addressed by URI and can be **templated**: `comunio://league/{id}/squad` style, with
  parameter completion.
- Responses can carry caching hints: `ttlMs` (freshness in ms) and `cacheScope`. Useful for market
  data that changes once a day.
- Change notifications are **opt-in**: the client opens a long-lived `subscriptions/listen` stream
  naming the notification types it wants (`toolsListChanged`, `resourceSubscriptions`, …). Delivery
  is best-effort, so clients are expected to poll too.

## 3. Client primitives — and what got deprecated

This is the part that most changes what is possible for us.

| Primitive | Status in `2026-07-28` |
| --- | --- |
| **Elicitation** | **Active.** Servers request input from the user mid-request. |
| Sampling | **Deprecated.** Servers can no longer lean on the host's LLM; integrate an LLM SDK directly instead. |
| Roots | **Deprecated.** Pass paths as tool parameters or config. |
| Logging (`notifications/message`) | **Deprecated.** Log to stderr (stdio) or OpenTelemetry. |

### Elicitation

The protocol-native way to ask the user something — including **asking for confirmation before
acting**.

Flow (the *Multi Round-Trip Requests* pattern):

1. Client calls `tools/call`.
2. Server replies with an `InputRequiredResult` whose `inputRequests` carries an
   `elicitation/create` request.
3. Client renders UI, user answers.
4. Client **retries the original request** with `inputResponses` attached, echoing back any
   `requestState` the server sent.
5. Server finishes and returns the real result.

Two modes:

- **Form mode** — a JSON Schema the client turns into a form. Example from the docs, which is almost
  exactly a bid confirmation:

  ```json
  {
    "method": "elicitation/create",
    "params": {
      "mode": "form",
      "message": "Please confirm your Barcelona vacation booking details:",
      "requestedSchema": {
        "type": "object",
        "properties": {
          "confirmBooking": { "type": "boolean", "description": "Confirm the booking" }
        },
        "required": ["confirmBooking"]
      }
    }
  }
  ```

- **URL mode** — the server hands over a URL, the user opens it out of band, and the data never
  passes through the client or the model context. Intended for credentials and third-party OAuth.

Hard rule from the spec: **form mode must never be used to request passwords, API keys, tokens or
payment credentials.** That rules out asking for Comunio credentials through an elicitation form.

Elicitation only works if the client declares the `elicitation` capability. We cannot assume it.

## 4. Authorization

- OAuth 2.1 (PRM document, `WWW-Authenticate` challenge, DCR, PKCE, audience-bound tokens) applies
  to **remote HTTP servers**. It authenticates the *user against our MCP server* — it has nothing to
  do with our server authenticating against Comunio.
- For **stdio servers the docs explicitly endorse environment-based credentials** or credentials
  handled by an embedded third-party library. No OAuth machinery needed.
- Relevant pitfalls if we ever go remote: never log `Authorization` headers or tokens, short-lived
  tokens, always validate audience, least-privilege scopes, never reuse the server's client secret
  for end-user flows, treat `Mcp-Session-Id` as untrusted and never tie authorization to it.

## 5. Python stack

From the official build-server tutorial:

- **Python 3.10+**, and **MCP Python SDK 2.0.0 or higher** (Tier 1 SDK,
  [py.sdk.modelcontextprotocol.io](https://py.sdk.modelcontextprotocol.io)).
- Install with `uv add "mcp[cli]"`.
- The entry class is `MCPServer` — note this is the 2.x API, not the older `FastMCP` naming:

  ```python
  from mcp.server import MCPServer

  mcp = MCPServer("weather")

  @mcp.tool()
  async def get_alerts(state: str) -> str:
      """Get weather alerts for a US state.

      Args:
          state: Two-letter US state code (e.g. CA, NY)
      """
      ...

  if __name__ == "__main__":
      mcp.run(transport="stdio")
  ```

- Tool schemas are derived from **type hints and docstrings**, so both are load-bearing, not
  decoration.
- HTTP client: the SDK depends on `httpx2`, so it comes for free.
- **Never write to stdout in a stdio server** — `print()` corrupts the JSON-RPC stream. Use
  `logging.getLogger(__name__)`, which writes to stderr.

> The exact `MCPServer` API above is copied from the docs. Verify it against the installed SDK
> version before relying on it.

## 6. What this means for Comunio MCP

Questions this reading raised. The first three are settled in
[architecture.md](architecture.md); the fourth still stands.

1. **Who does the reasoning?** Settled: the host. With sampling deprecated the server cannot borrow
   the host's LLM, and it does not try to replace it either — the tools serve data and the client
   decides (Decision 1).
2. **How is approval enforced?** Settled: by the host, outside this project. The server declares
   effects through annotations and descriptions and runs no confirmation of its own — no
   `elicitation`, no proposal step (Decision 2).
3. **Statelessness.** Settled by not needing it. Nothing has to survive between two calls, because
   nothing is split across two calls.
4. **Tools or resources for read data?** Still open. Squad and market fit the resource model, but
   resources are application-controlled and unevenly supported by clients. Tools are the safe
   default; resources could be added on top.
5. **Credentials.** stdio + environment variables is the documented path, and elicitation form mode
   is explicitly forbidden for this.

## Sources

- [Architecture overview](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
- [Server concepts](https://modelcontextprotocol.io/docs/2026-07-28/learn/server-concepts)
- [Client concepts](https://modelcontextprotocol.io/docs/2026-07-28/learn/client-concepts)
- [Versioning](https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning)
- [Build a server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server)
- [SDKs](https://modelcontextprotocol.io/docs/2026-07-28/sdk)
- [Authorization tutorial](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization)
