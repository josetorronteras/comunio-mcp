"""Put one of the manager's players up for sale."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import list_on_market
from comunio_mcp.comunio.models import ListingResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # Reversible: `unlist_player_from_market` takes it straight back off.
            destructive_hint=False,
            idempotent_hint=False,
        )
    )
    async def list_player_on_market(
        ctx: Context[AppContext], player_id: int, price: int
    ) -> ListingResult:
        """Put one of the manager's own players up for sale at the given asking price.

        **This changes the manager's team.** Confirm the player and the price with the
        user before calling it. Ids come from `get_squad`; `get_player` gives Comunio's
        suggested price for comparison.

        Listing is reversible — the player can be taken back off the market — but any
        offers received in the meantime are real.

        Check `placed` and `rejected` in the result rather than assuming it worked:
        Comunio can refuse an individual player while reporting overall success.
        """
        app = ctx.request_context.lifespan_context
        return await list_on_market(
            require_session(app), require_comunio(app), player_id, price
        )
