"""Read the league table."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Standings
from comunio_mcp.comunio.standings import fetch_standings
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_standings(ctx: Context[AppContext]) -> Standings:
        """Get the league table: every manager with their points, squad value and whether
        their budget is in the red.

        Rows come best first, with `rank` filled in and `is_me` marking the signed-in
        manager. `negative_budget` says which rivals cannot outbid anyone right now, and
        `manager_id` can be used to look up a rival's squad.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_standings(require_session(app), require_comunio(app))
