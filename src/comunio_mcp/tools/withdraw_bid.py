"""Withdraw one of the manager's own pending bids."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import withdraw_bid as withdraw
from comunio_mcp.comunio.models import WithdrawResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Withdraw a bid",
        annotations=ToolAnnotations(
            read_only_hint=False,
            # The bid is gone, but a new one can be placed while the market is open.
            destructive_hint=False,
            idempotent_hint=False,
        )
    )
    async def withdraw_bid(ctx: Context[AppContext], offer_id: int) -> WithdrawResult:
        """Withdraw a bid the manager has placed, so it is no longer in the running.

        **This changes what the manager has committed to.** Confirm which bid with the
        user before calling it. Ids come from `get_offers`; only offers whose `direction`
        is `outgoing` can be withdrawn.

        Refuses outright if the id belongs to an offer *for* one of the manager's players
        rather than a bid they made. Comunio uses the same request for both, so telling
        them apart is done here rather than left to chance.

        A withdrawn bid cannot be restored, but a new one can be placed while the market
        is still open.
        """
        app = ctx.request_context.lifespan_context
        return await withdraw(require_session(app), require_comunio(app), offer_id)
