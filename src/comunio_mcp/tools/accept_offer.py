"""Accept an offer for one of the manager's players."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import accept_offer as accept
from comunio_mcp.comunio.models import AcceptResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # The only one. The player is gone the moment this returns.
            destructive_hint=True,
            idempotent_hint=False,
        )
    )
    async def accept_offer(ctx: Context[AppContext], offer_id: int) -> AcceptResult:
        """Accept an offer for one of the manager's players, selling them.

        **This cannot be undone.** Unlike a bid, which queues until the transfer round and
        can be withdrawn, an acceptance takes effect the moment it is made. The player
        leaves the squad and there is nothing to reverse it with.

        Get the user's explicit agreement first, and tell them two things before asking:
        who is being sold, and how the price compares to what the player is worth.
        `get_offers` reports that as `premium` and `premium_pct` — a negative value means
        the offer is **below** the player's market value, which is common and easy to miss.

        Ids come from `get_offers`; only offers whose `direction` is `incoming` can be
        accepted. The player and the price are taken from the offer itself, never passed
        in, so what is accepted is exactly what was offered.

        Check `ok` and `message` in the result. Comunio can report overall success while
        rejecting the acceptance itself.
        """
        app = ctx.request_context.lifespan_context
        return await accept(require_session(app), require_comunio(app), offer_id)
