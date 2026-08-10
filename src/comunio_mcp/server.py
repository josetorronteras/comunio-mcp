"""The MCP server instance and the registration of every tool it exposes."""

from mcp.server import MCPServer

from comunio_mcp.context import lifespan
from comunio_mcp.metadata import SERVER_NAME, SERVER_VERSION
from comunio_mcp.tools import (
    accept_offer,
    account,
    change_bid,
    list_on_market,
    market,
    offers,
    ping,
    place_bid,
    player,
    set_asking_price,
    squad,
    standings,
    transfers,
    unlist_from_market,
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

ping.register(mcp)
account.register(mcp)
squad.register(mcp)
player.register(mcp)
standings.register(mcp)
market.register(mcp)
offers.register(mcp)
transfers.register(mcp)

# Actions that change something.
list_on_market.register(mcp)
unlist_from_market.register(mcp)
set_asking_price.register(mcp)
place_bid.register(mcp)
change_bid.register(mcp)
accept_offer.register(mcp)
withdraw_bid.register(mcp)
