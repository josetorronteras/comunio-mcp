"""Change the asking price of a player already listed on the market."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import set_asking_price as change_price
from comunio_mcp.comunio.models import AskingPriceResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            # Setting the same price twice leaves the same price.
            idempotent_hint=True,
        )
    )
    async def change_listing_price(
        ctx: Context[AppContext], player_id: int, price: int
    ) -> AskingPriceResult:
        """Change what the manager is asking for a player they already have listed on the
        market.

        **This changes the manager's team.** Confirm the player and the new price with the
        user before calling it. **The player must already be listed** — use
        `list_player_on_market` first if they are not; this tool cannot put anyone up for
        sale.

        This sets the *manager's own* asking price. It has nothing to do with the
        `recommended_price` that `get_market` and `get_player` report, which is Comunio's
        suggestion and cannot be changed.

        Comunio answers with a bare `true` here rather than any detail, so `ok` is all
        there is to go on.
        """
        app = ctx.request_context.lifespan_context
        return await change_price(
            require_session(app), require_comunio(app), player_id, price
        )
