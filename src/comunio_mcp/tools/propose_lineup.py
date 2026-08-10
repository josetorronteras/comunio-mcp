"""Propose an optimal lineup, without applying it."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.lineup import TACTICS, best_lineup
from comunio_mcp.comunio.models import LineupProposal, LineupProposalSlot
from comunio_mcp.comunio.squad import fetch_squad
from comunio_mcp.context import AppContext, require_comunio, require_proposals, require_session

FORMATIONS = ", ".join(sorted(TACTICS))


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # Never applied by this tool; nothing about the manager's team changes.
            destructive_hint=False,
            # Squad state can change between calls, so the same input is not guaranteed
            # to produce the same proposal.
            idempotent_hint=False,
        )
    )
    async def propose_lineup(
        ctx: Context[AppContext], tactic: str | None = None
    ) -> LineupProposal:
        """Work out the best starting eleven from the manager's squad and store it as a
        proposal. **Never calls a write endpoint** — nothing about the manager's team
        changes until `execute_lineup` is called with the `proposal_id` this returns.

        Deterministic: ranks each position's players by availability first, then season
        average points, and fills the formation's slots from the top. A player who is not
        `ACTIVE` (injured, suspended, and similar) is only used when there are not enough
        available players for that position — preferred over leaving the slot empty.

        `tactic` is one of: 442, 343, 352, 433, 451 — read as defenders, midfielders,
        strikers. Leave it unset to let the tool try all five and pick the one with the
        highest points net of the empty-slot penalty.

        The proposal expires 30 minutes after being made. Show the user `summary` before
        calling `execute_lineup` — nothing should be applied without that.
        """
        app = ctx.request_context.lifespan_context
        squad = await fetch_squad(require_session(app), require_comunio(app))
        plan = best_lineup(squad.players, tactic=tactic)

        proposal = require_proposals(app).create(
            kind="lineup", summary=plan.summary, payload=plan.payload
        )

        return LineupProposal(
            proposal_id=proposal.id,
            tactic=plan.tactic,
            fielded=[
                LineupProposalSlot(
                    slot=slot,
                    position=position,
                    player_id=player.id,
                    player=player.name,
                    average_points=player.average_points,
                    status=player.status,
                )
                for slot, position, player in plan.fielded
            ],
            empty_slots=plan.empty_slots,
            estimated_points=plan.estimated_points,
            estimated_penalty_points=plan.penalty_points,
            summary=plan.summary,
            expires_at=proposal.expires_at,
        )
