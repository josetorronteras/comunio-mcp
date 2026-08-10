"""Set the lineup for the coming matchday."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.lineup import TACTICS
from comunio_mcp.comunio.lineup import set_lineup as apply_lineup
from comunio_mcp.comunio.models import LineupResult
from comunio_mcp.context import AppContext, require_comunio, require_session

FORMATIONS = ", ".join(sorted(TACTICS))


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # A lineup can be set again until the matchday starts.
            destructive_hint=False,
            # Sending the same lineup twice leaves the same lineup.
            idempotent_hint=True,
        )
    )
    async def set_lineup(
        ctx: Context[AppContext],
        tactic: str,
        keeper: int | None = None,
        defenders: list[int] | None = None,
        midfielders: list[int] | None = None,
        strikers: list[int] | None = None,
    ) -> LineupResult:
        """Set the manager's formation and starting eleven.

        **This replaces the current lineup.** Confirm the formation and the players with
        the user before calling it.

        `tactic` is one of: 442, 343, 352, 433, 451 — read as defenders, midfielders,
        strikers. Players are given by position and ids come from `get_squad`; the slot
        numbers Comunio wants are worked out here.

        A partial lineup is allowed. Comunio deducts **four points for every empty slot**,
        and the result says how many were left and what that costs.

        Players who are injured or suspended can still be fielded — Comunio permits it —
        so they are not refused, but the result lists them under `unavailable`. Check
        `status` in `get_squad` before choosing.

        Refused before anything is sent if the formation is not one Comunio accepts, if
        there are more players than the formation has room for, if a player is not in the
        squad, if one appears twice, or if someone is put in a position they do not play.

        The lineup can be set again until the matchday starts.
        """
        app = ctx.request_context.lifespan_context
        return await apply_lineup(
            require_session(app),
            require_comunio(app),
            tactic=tactic,
            keeper=keeper,
            defenders=defenders,
            midfielders=midfielders,
            strikers=strikers,
        )
