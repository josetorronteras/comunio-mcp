"""Read the manager's squad."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Squad
from comunio_mcp.comunio.squad import fetch_squad
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_squad(ctx: Context[AppContext], manager_id: int | None = None) -> Squad:
        """Get every player in a squad, with availability, scoring, prices and lineup
        state. Defaults to the signed-in manager's own squad.

        Pass `manager_id` to inspect a rival's squad instead — the ids come from
        `get_standings`. Rival squads are fully visible: prices, injuries and depth. What
        is not visible is `recommended_price`, which Comunio only gives for your own
        players.

        Per player: `position` and `club`; `status` with `status_info` naming an injury;
        `points`, `last_points` and `average_points`; `quoted_price` and
        `recommended_price`; whether they are `linedup` or a `substitute`; whether they
        are `on_market`; and `next_match` with its kick-off time.

        `summary` counts what lineup rules are checked against, `tactic` is the formation
        set, and `is_mine` says whose squad came back.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_squad(require_session(app), require_comunio(app), manager_id)
