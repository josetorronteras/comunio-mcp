"""Read the transfer market."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.market import fetch_market
from comunio_mcp.comunio.models import Market
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_market(ctx: Context[AppContext]) -> Market:
        """Get every player currently up for sale, with prices, price trend and who is
        selling.

        `closes_at` is when the current round of transfers is processed — bids have to be
        in before it. Per listing, `from_computer` marks players Comunio is selling itself
        rather than a rival, `is_mine` marks the manager's own listings, which are not
        buyable, and `trend` shows which way the price is moving.

        Compare `quoted_price` against `recommended_price` to judge an asking price, and
        check `get_account` for the budget that bounds any bid.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_market(require_session(app), require_comunio(app))
