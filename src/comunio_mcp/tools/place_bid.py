"""Bid for a player on the market."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.actions import place_bid as bid
from comunio_mcp.comunio.models import BidResult
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # The bid queues until the transfer round and can be withdrawn before then.
            destructive_hint=False,
            idempotent_hint=False,
        )
    )
    async def place_bid(ctx: Context[AppContext], player_id: int, price: int) -> BidResult:
        """Bid for a player on the market.

        **This commits the manager's money.** Confirm the player and the amount with the
        user before calling it, and say what they would have left.

        The bid does not take effect straight away: it waits for the next transfer round,
        which `get_market` reports as `closes_at`. Until then it can be changed with
        `change_bid` or pulled with `withdraw_bid`.

        Sizing the bid: compare against `credit` from `get_offers`, not `budget` from
        `get_account` — the league's credit factor makes them different numbers. Comunio's
        `credit` does **not** subtract bids already outstanding, so check
        `credit_committed` in the result for what is already promised. What players
        actually sell for is in `get_transfers`; `quoted_price` is only an asking price.

        The amount is **not** checked against credit here. Comunio enforces its own limit
        and answers "Credit exceeded", so a bid it would accept is never refused by this
        tool. Refused before anything is sent only if the player is not on the market or
        is one of the manager's own listings.

        Check `ok` and `message` in the result. Comunio can report overall success while
        rejecting the bid itself.
        """
        app = ctx.request_context.lifespan_context
        return await bid(require_session(app), require_comunio(app), player_id, price)
