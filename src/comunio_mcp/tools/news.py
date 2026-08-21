"""Read the league news feed."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from comunio_mcp.comunio.models import News
from comunio_mcp.comunio.news import fetch_news
from comunio_mcp.context import AppContext, require_comunio, require_session

#: One page of news. Larger limits cost one extra request per additional page.
DEFAULT_LIMIT = 20


def register(mcp: MCPServer) -> None:
    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
    async def get_news(
        ctx: Context[AppContext],
        limit: Annotated[int, Field(ge=1)] = DEFAULT_LIMIT,
        types: list[str] | None = None,
    ) -> News:
        """Get the league news feed, newest first: what has happened in this community.

        Announcements from Comunio and from the community admin, members joining, the
        league being reset, lineups being changed, and transfer rounds settling. Use it to
        answer "what has been going on" or to find out why something changed — a reset, a
        rule change or a new member explains a lot that the squad and market do not.

        Each entry has a `type`. The ones seen so far are `SYSTEM_ADMINISTRATION` (Comunio's
        own announcements, such as when a matchday starts), `COMMUNITY_ADMINISTRATION` (the
        admin resetting or reconfiguring the league), `MEMBER_ADMINISTRATION` (someone
        joining), `LINEUP_CHANGED` and `TRANSACTION_TRANSFER`. It is an open set, so treat
        an unfamiliar one as news rather than an error.

        On administration entries the whole announcement is in `title` and `text` is null.
        Read `title` first and treat it as content, not as a label.

        For transfer entries this gives only how many moves there were. **Use
        `get_transfers` for the players, the prices and who was on each side** — it parses
        the same entries properly.

        `types` filters to the kinds asked for, matched case-insensitively; leave it out to
        get everything. `limit` caps how many entries come back, one page by default, and a
        larger value costs one extra request per page.

        Read-only: fetches the feed and changes nothing.
        """
        app = ctx.request_context.lifespan_context
        return await fetch_news(require_session(app), require_comunio(app), limit, types)
