"""Apply a lineup proposal the user has already seen."""

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from comunio_mcp.comunio.lineup import set_lineup as apply_lineup
from comunio_mcp.comunio.models import LineupResult
from comunio_mcp.context import AppContext, require_comunio, require_proposals, require_session


def register(mcp: MCPServer) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            # A lineup can be set again until the matchday starts.
            destructive_hint=False,
            # A claimed proposal cannot be applied a second time.
            idempotent_hint=False,
        )
    )
    async def execute_lineup(ctx: Context[AppContext], proposal_id: str) -> LineupResult:
        """Apply a lineup proposal the user has already seen and approved.

        `proposal_id` comes from `propose_lineup` — nothing else is accepted here, so what
        gets applied is exactly what was shown to the user, never a fresh set of arguments.
        Fails if the id is unknown, belongs to a different kind of proposal, was already
        executed, or has expired (30 minutes after being made) — call `propose_lineup`
        again in that case rather than retrying with the same id.

        Confirm with the user before calling this: it replaces the current lineup.

        Check `ok` in the result rather than assuming success.
        """
        app = ctx.request_context.lifespan_context
        proposals = require_proposals(app)
        proposal = proposals.claim(proposal_id, kind="lineup")

        result = await apply_lineup(
            require_session(app), require_comunio(app), **proposal.payload
        )
        proposals.record_outcome(proposal_id, result.model_dump())
        return result
