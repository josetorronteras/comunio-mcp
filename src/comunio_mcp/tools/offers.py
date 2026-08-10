"""Read open transfer offers."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Offers
from comunio_mcp.comunio.offers import fetch_offers
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_offers(ctx: Context[AppContext]) -> Offers:
        """Get every open transfer offer, and the manager's spending power.

        `credit` is what can actually be spent and is **not** the same as the budget in
        `get_account`: the league's credit factor lets it exceed cash in hand. Use this
        number when sizing a bid.

        Each offer says which way it goes — `incoming` when somebody wants one of the
        manager's players, `outgoing` when the manager is bidding — and how the price
        compares to the player's market value, via `premium` and `premium_pct`. A negative
        premium is an offer below what the player is worth.

        Read-only: fetches current state and changes nothing. Accepting, declining or
        withdrawing an offer is not possible through this tool.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_offers(require_session(app), require_comunio(app))
