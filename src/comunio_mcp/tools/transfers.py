"""Read completed transfers."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Transfers
from comunio_mcp.comunio.transfers import fetch_transfers
from comunio_mcp.context import AppContext, require_comunio, require_session

#: One page of news. Larger limits cost one extra request per additional page.
DEFAULT_LIMIT = 20


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_transfers(ctx: Context[AppContext], limit: int = DEFAULT_LIMIT) -> Transfers:
        """Get transfers that have already completed, newest first, with what was
        actually paid.

        This is settled prices rather than quotes: what players really went for in this
        league. Use it to calibrate a bid, since the market only says what a player is
        listed at.

        `from_computer` means bought from Comunio, `to_computer` sold back to it, and
        `involves_me` marks the signed-in manager's own deals. `summary` totals each kind
        and the money that changed hands.

        `limit` caps how many transfers come back. The default is one page; asking for
        more costs an extra request per page, so raise it only when the extra history is
        actually wanted.

        Read-only: fetches history and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_transfers(require_session(app), require_comunio(app), limit)
