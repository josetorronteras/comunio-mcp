"""The MCP server instance and the registration of every tool it exposes."""

from mcp.server import MCPServer

from comunio_mcp.context import lifespan
from comunio_mcp.metadata import SERVER_NAME, SERVER_VERSION
from comunio_mcp.tools import (
    accept_offer,
    account,
    change_bid,
    change_listing_price,
    execute_lineup,
    list_on_market,
    market,
    offers,
    place_bid,
    player,
    propose_lineup,
    set_lineup,
    squad,
    standings,
    transfers,
    unlist_from_market,
    watchlist,
    withdraw_bid,
)

mcp = MCPServer(
    SERVER_NAME,
    version=SERVER_VERSION,
    lifespan=lifespan,
    instructions=(
        "Read and operate on a Comunio fantasy football team. Tools whose name starts "
        "with get_ only read and are always safe to call. Every other tool changes the "
        "manager's team or spends their money: confirm the details with the user before "
        "calling one, and report what the result says actually happened rather than "
        "assuming success."
    ),
)

account.register(mcp)
squad.register(mcp)
player.register(mcp)
standings.register(mcp)
market.register(mcp)
offers.register(mcp)
transfers.register(mcp)
watchlist.register(mcp)

# Actions that change something.
list_on_market.register(mcp)
unlist_from_market.register(mcp)
change_listing_price.register(mcp)
place_bid.register(mcp)
change_bid.register(mcp)
accept_offer.register(mcp)
set_lineup.register(mcp)
withdraw_bid.register(mcp)

# Propose/execute pairs. propose_* is a deterministic optimiser that stores a proposal;
# execute_* applies a proposal the user has already seen, and decides nothing itself.
propose_lineup.register(mcp)
execute_lineup.register(mcp)
