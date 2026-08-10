"""Liveness tool. Exists to prove the server is reachable and wired correctly."""

from datetime import UTC, datetime

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from comunio_mcp.metadata import SERVER_NAME, SERVER_VERSION


class Pong(BaseModel):
    server: str = Field(description="Name this server registered with MCP")
    version: str = Field(description="Version of the running comunio-mcp package")
    timestamp: str = Field(description="UTC time the server answered, ISO 8601")


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def ping() -> Pong:
        """Check that the Comunio MCP server is alive and reachable.

        Returns the server name, its version and the current UTC time. Reads
        nothing from Comunio and changes nothing.
        """
        return Pong(
            server=SERVER_NAME,
            version=SERVER_VERSION,
            timestamp=datetime.now(UTC).isoformat(),
        )
