"""Change the amount of a bid already placed."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import change_bid as change
from comunio_mcp.comunio.models import BidResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # Still queued until the transfer round, and still withdrawable.
            destructive_hint=False,
            idempotent_hint=False,
        )
    )
    async def change_bid(ctx: Context[AppContext], offer_id: int, price: int) -> BidResult:
        """Change the amount of a bid the manager has already placed.

        **This changes what the manager has committed.** Confirm the new amount with the
        user before calling it, and say what the old one was.

        Ids come from `get_offers`; only offers whose `direction` is `outgoing` can be
        changed. The player is taken from the offer itself rather than passed in, so a
        change cannot end up pointing at a different player.

        Like a new bid, the change waits for the next transfer round and can still be
        pulled with `withdraw_bid` until then.

        Refused before anything is sent if the id is unknown, if it belongs to an offer
        *for* one of the manager's players, or if the new amount exceeds available credit.

        Check `ok` and `message` in the result rather than assuming success.
        """
        app = ctx.request_context.lifespan_context
        return await change(require_session(app), require_comunio(app), offer_id, price)
