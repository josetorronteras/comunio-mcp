"""Comunio MCP server package."""

import logging
import sys


def main() -> None:
    """Entry point. Runs the server over stdio.

    Logging goes to stderr on purpose: anything written to stdout would corrupt
    the JSON-RPC stream and break the server.
    """
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from comunio_mcp.server import mcp

    mcp.run(transport="stdio")
