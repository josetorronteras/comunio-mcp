"""Resources shared by every tool call, built once per server process."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx2
from mcp.server import MCPServer

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient, default_headers
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import ConfigError, Settings
from comunio_mcp.proposals import ProposalStore

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15.0


@dataclass
class AppContext:
    #: None when credentials are not configured. The server still starts, so a client
    #: sees a working server and a clear error instead of a process that dies at boot.
    comunio: ComunioClient | None
    session: Session | None = None
    #: Where proposals wait between being made and being executed. Present even without
    #: credentials, since it needs nothing from Comunio.
    proposals: ProposalStore | None = None


@asynccontextmanager
async def lifespan(_server: MCPServer) -> AsyncIterator[AppContext]:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        logger.warning("Comunio tools are disabled: %s", exc)
        yield AppContext(comunio=None)
        return

    proposals = ProposalStore(settings.proposals_path)
    try:
        async with httpx2.AsyncClient(
            headers=default_headers(settings), timeout=REQUEST_TIMEOUT_SECONDS
        ) as http:
            auth = ComunioAuth(http, settings)
            client = ComunioClient(http, auth)
            yield AppContext(comunio=client, session=Session(client), proposals=proposals)
    finally:
        proposals.close()


_MISSING_CREDENTIALS = (
    "This tool needs Comunio credentials. Set COMUNIO_USERNAME and COMUNIO_PASSWORD "
    "in the server environment; see docs/setup.md."
)


def require_comunio(app: AppContext) -> ComunioClient:
    """Return the Comunio client, or fail with a message that says how to fix it."""
    if app.comunio is None:
        raise RuntimeError(_MISSING_CREDENTIALS)
    return app.comunio


def require_session(app: AppContext) -> Session:
    """Return the Comunio session, or fail with a message that says how to fix it."""
    if app.session is None:
        raise RuntimeError(_MISSING_CREDENTIALS)
    return app.session


def require_proposals(app: AppContext) -> ProposalStore:
    """Return the proposal store, or fail with a message that says how to fix it."""
    if app.proposals is None:
        raise RuntimeError(_MISSING_CREDENTIALS)
    return app.proposals
