"""Read one player's detail sheet."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import PlayerDetail
from comunio_mcp.comunio.player import fetch_player
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Player detail",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def get_player(ctx: Context[AppContext], player_id: int) -> PlayerDetail:
        """Get everything Comunio knows about one player. Ids come from `get_squad`,
        `get_market` or `get_offers`.

        Beyond the price and availability the squad already gives: season-by-season
        `history` going back years, the `record` of goals, cards and man-of-the-match
        awards, `averages` including a recent-form window, the next three fixtures, what
        the current owner paid, and the `buyout_clause` — what taking the player from
        their owner without consent would cost.

        `status_meaning` spells out the status code, and `available` is true only when the
        player can actually be counted on.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_player(require_session(app), require_comunio(app), player_id)
