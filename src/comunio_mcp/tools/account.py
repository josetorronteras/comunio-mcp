"""Read the signed-in manager's account and the rules of their league."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import AccountSnapshot
from comunio_mcp.context import AppContext, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Account and league rules",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def get_account(ctx: Context[AppContext]) -> AccountSnapshot:
        """Get the manager's current budget, squad totals and formation, plus the
        league rules that decide which moves are legal.

        Start here. `budget` bounds any bid, `tactic` and `team_count_linedup` say what
        the lineup looks like now, and the rules cover bidding mechanics (notably
        `second_highest_offers`), sale limits and bans.

        Read-only: fetches current state and changes nothing.
        """
        session = require_session(ctx.request_context.lifespan_context)
        return await session.snapshot()
