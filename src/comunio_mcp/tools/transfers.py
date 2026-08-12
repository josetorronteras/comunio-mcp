"""Read completed transfers."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Transfers
from comunio_mcp.comunio.transfers import DEFAULT_LIMIT, fetch_transfers
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_transfers(ctx: Context[AppContext], limit: int = DEFAULT_LIMIT) -> Transfers:
        """Get transfers that have already completed, newest first, with what was
        actually paid.

        This is settled prices rather than quotes: what players really went for in this
        league. Use it to calibrate a bid, since the market only says what a player is
        listed at. Each transfer also carries `quoted_price`, what the player was valued
        at, so paying over or under the odds is visible without another call.

        `from_computer` means bought from Comunio, `to_computer` sold back to it, and
        `involves_me` marks the signed-in manager's own deals. `offered_at` is when the
        bid went in and `settled_at` when it went through. `summary` totals each kind and
        the money that changed hands.

        `limit` caps how many transfers come back and **defaults to 20, which is a default
        rather than a maximum**: this endpoint returns as many as it is asked for. Raise it
        to look further back — a larger value costs one extra request only when there is
        more history than one page holds.

        Read-only: fetches history and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_transfers(require_session(app), require_comunio(app), limit)
