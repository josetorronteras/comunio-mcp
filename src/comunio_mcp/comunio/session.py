"""The index endpoint: `GET /`.

Comunio's root is a HAL-style index. It returns the signed-in manager, their league, and
`_links` — a map of roughly ninety named routes covering the whole API. That map is how
every other endpoint is found, so no path is hardcoded anywhere else.

Two lifetimes, deliberately kept apart:

* **Routing** (ids and links) is immutable for the life of the process, so it is fetched
  once and cached.
* **State** (budget, squad value, formation) changes constantly and is never cached. A
  stale budget is a miscalculated bid; one extra HTTP call is cheaper than that.
"""

import asyncio
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import AccountSnapshot

logger = logging.getLogger(__name__)

INDEX_PATH = "/"

#: Links come in two flavours, sometimes for sibling routes: some already carry the real
#: ids, others keep `:placeholder` segments. Anything left unresolved is a bug, so the
#: resolver refuses to return such a URL.
_PLACEHOLDER = re.compile(r":([A-Za-z][A-Za-z0-9_]*)")


class SessionError(RuntimeError):
    """The index response was not shaped the way we expect."""


@dataclass(frozen=True)
class SessionInfo:
    user_id: str
    community_id: str
    links: Mapping[str, str]


class Session:
    def __init__(self, client: ComunioClient) -> None:
        self._client = client
        self._info: SessionInfo | None = None
        self._lock = asyncio.Lock()

    async def info(self) -> SessionInfo:
        """Routing information, fetched once and reused."""
        async with self._lock:
            if self._info is None:
                self._info = _parse_info(await self._client.get(INDEX_PATH))
                logger.info(
                    "Session ready: user %s, community %s, %d links",
                    self._info.user_id,
                    self._info.community_id,
                    len(self._info.links),
                )
            return self._info

    async def snapshot(self) -> AccountSnapshot:
        """Current account and league state. Always fetched fresh."""
        payload = await self._client.get(INDEX_PATH)

        async with self._lock:
            # The routing half of the same response is free, so keep it.
            if self._info is None:
                self._info = _parse_info(payload)

        return _parse_snapshot(payload)

    async def link(self, name: str, **params: str) -> str:
        """Resolve a named link to a path, filling in `:placeholder` segments.

        `userId` and `communityId` default to the signed-in manager and their league, so
        callers only pass what is genuinely variable.
        """
        info = await self.info()

        href = info.links.get(name)
        if href is None:
            raise SessionError(f"Unknown link {name!r}")

        values = {"userId": info.user_id, "communityId": info.community_id, **params}
        resolved = _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), href)

        missing = _PLACEHOLDER.findall(resolved)
        if missing:
            raise SessionError(f"Link {name!r} still needs {', '.join(sorted(set(missing)))}")

        return resolved


def _parse_info(payload: Any) -> SessionInfo:
    try:
        user_id = str(payload["user"]["id"])
        community_id = str(payload["community"]["id"])
        links = {name: target["href"] for name, target in payload["_links"].items()}
    except (KeyError, TypeError) as exc:
        raise SessionError(f"Unexpected index response: {exc}") from exc

    return SessionInfo(
        user_id=user_id, community_id=community_id, links=MappingProxyType(links)
    )


def _parse_snapshot(payload: Any) -> AccountSnapshot:
    try:
        community = payload["community"]
        # Rules arrive wrapped: community.rules.items holds the actual settings.
        rules = community["rules"]["items"]
        return AccountSnapshot.model_validate(
            {
                "account": payload["user"],
                "community": {"id": community["id"], "name": community["name"], "rules": rules},
            }
        )
    except (KeyError, TypeError) as exc:
        raise SessionError(f"Unexpected index response: {exc}") from exc
