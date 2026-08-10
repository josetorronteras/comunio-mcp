import asyncio

from comunio_mcp.metadata import SERVER_NAME
from comunio_mcp.server import mcp


def test_server_identity() -> None:
    assert mcp.name == SERVER_NAME


def test_ping_is_registered_and_read_only() -> None:
    tools = asyncio.run(mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert "ping" in by_name
    assert by_name["ping"].annotations.read_only_hint is True


def test_ping_answers() -> None:
    result = asyncio.run(mcp.call_tool("ping", {}))

    assert result is not None
