"""Read the watchlist and change what is on it."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.models import Watchlist, WatchResult
from comunio_mcp.comunio.watchlist import fetch_watchlist
from comunio_mcp.comunio.watchlist import unwatch_player as remove_from_watchlist
from comunio_mcp.comunio.watchlist import watch_player as add_to_watchlist
from comunio_mcp.context import AppContext, require_comunio, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        title="Watchlist",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    async def get_watchlist(ctx: Context[AppContext]) -> Watchlist:
        """Get the players the manager is keeping an eye on.

        A shortlist, not a commitment: watching a player does nothing to the squad or the
        budget. Use `get_market` to see which of them are actually for sale.

        Read-only: fetches current state and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_watchlist(require_session(app), require_comunio(app))

    @mcp.tool(
        title="Watch a player",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            # Watching an already watched player leaves them watched.
            idempotent_hint=True,
        )
    )
    async def watch_player(ctx: Context[AppContext], player_id: int) -> WatchResult:
        """Add a player to the manager's watchlist.

        Harmless: it commits nothing and spends nothing, it only marks the player as one
        to keep an eye on. Ids come from `get_market`, `get_squad` or `get_standings`.
        """
        app = ctx.request_context.lifespan_context
        return await add_to_watchlist(require_session(app), require_comunio(app), player_id)

    @mcp.tool(
        title="Stop watching a player",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
        )
    )
    async def unwatch_player(ctx: Context[AppContext], player_id: int) -> WatchResult:
        """Remove a player from the manager's watchlist.

        Harmless: it changes nothing about the squad, the budget or any offer. Ids come
        from `get_watchlist`.
        """
        app = ctx.request_context.lifespan_context
        return await remove_from_watchlist(
            require_session(app), require_comunio(app), player_id
        )
