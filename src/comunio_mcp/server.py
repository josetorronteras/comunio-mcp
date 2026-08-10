"""The MCP server instance and the registration of every tool it exposes."""

from mcp.server import MCPServer

from comunio_mcp.context import lifespan
from comunio_mcp.metadata import SERVER_NAME, SERVER_VERSION
from comunio_mcp.tools import ping

mcp = MCPServer(
    SERVER_NAME,
    version=SERVER_VERSION,
    lifespan=lifespan,
    instructions=(
        "Read and operate on a Comunio fantasy football team. Tools are layered: "
        "get_* only read, propose_* compute a candidate move without sending anything, "
        "and execute_* apply a proposal the user has already approved."
    ),
)

ping.register(mcp)
