"""Take one of the manager's players back off the market."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import unlist_from_market
from comunio_mcp.comunio.models import UnlistResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Take a player off the market",
        annotations=ToolAnnotations(
            read_only_hint=False,
            # Reversible: `list_player_on_market` puts it straight back up.
            destructive_hint=False,
            idempotent_hint=False,
        )
    )
    async def unlist_player_from_market(
        ctx: Context[AppContext], player_id: int
    ) -> UnlistResult:
        """Take one of the manager's own players back off the market, so it is no longer
        for sale.

        **This changes the manager's team.** Confirm which player with the user before
        calling it. Ids come from `get_market`, where the manager's own listings are the
        ones marked `is_mine`.

        Any offers already received for that player are not cancelled by this — check
        `get_offers`.

        Comunio reports no per-player detail here, only an overall status, so `unlisted`
        is what was asked for rather than what was confirmed. Call `get_market` if it
        matters.
        """
        app = ctx.request_context.lifespan_context
        return await unlist_from_market(require_session(app), require_comunio(app), player_id)
