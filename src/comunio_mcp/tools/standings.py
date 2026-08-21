"""Read the league table."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Standings
from comunio_mcp.comunio.standings import Period, fetch_standings
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="League table",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def get_standings(
        ctx: Context[AppContext],
        period: Period = "total",
    ) -> Standings:
        """Get the league table: every manager with their points, squad value and whether
        their budget is in the red.

        Rows come best first, with `rank` filled in and `is_me` marking the signed-in
        manager, and `manager_id` can be used to look up a rival's squad.

        `period` picks which table. `total` is the season standings. **`live` is the one
        to ask for while a matchday is being played**: only it fills `live_points` and
        `players_possibly_scoring`, and only it reports `negative_budget` correctly —
        under `total` that flag reads false for everyone, including managers who are
        actually in the red and will therefore score nothing this matchday.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_standings(require_session(app), require_comunio(app), period)
