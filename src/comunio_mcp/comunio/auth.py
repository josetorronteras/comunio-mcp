"""Authentication against api.comunio.es.

Deliberately *not* an MCP tool. Tools are model-controlled, so a `login` tool would
let the model trigger authentication on a whim and would put the tokens in its
context. Authentication is plumbing that sits underneath the tools.

Nothing here ever logs a token value.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx2

from comunio_mcp.config import Settings

logger = logging.getLogger(__name__)

LOGIN_URL = "https://api.comunio.es/login"

# Tokens are refreshed slightly before they actually expire, so a request never
# leaves with a token that dies in flight.
EXPIRY_MARGIN = timedelta(seconds=60)


class AuthError(RuntimeError):
    """Login or refresh was rejected by Comunio."""


@dataclass(frozen=True)
class Token:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def is_usable(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) < self.expires_at - EXPIRY_MARGIN

    @classmethod
    def from_payload(cls, payload: dict, now: datetime | None = None) -> "Token":
        try:
            access_token = payload["access_token"]
            refresh_token = payload["refresh_token"]
            expires_in = int(payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthError(f"Unexpected login response shape: {sorted(payload)}") from exc

        issued_at = now or datetime.now(UTC)
        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=issued_at + timedelta(seconds=expires_in),
        )


class ComunioAuth:
    """Keeps a usable access token, logging in and refreshing as needed.

    The token lives in memory only. MCP is a stateless *protocol*, but the server
    process stays alive between calls, so there is no need to put a rotating secret
    on disk.
    """

    def __init__(self, http: httpx2.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings
        self._token: Token | None = None
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        """Return a valid access token, acquiring or refreshing it if necessary."""
        async with self._lock:
            token = self._token
            if token is not None and token.is_usable():
                return token.access_token

            if token is not None:
                try:
                    self._token = await self._refresh(token)
                except AuthError:
                    # Refresh tokens rotate and can be rejected. A full login is the
                    # documented way back in.
                    logger.info("Refresh rejected, falling back to a full login")
                    self._token = await self._login()
            else:
                self._token = await self._login()

            return self._token.access_token

    @property
    def expires_at(self) -> datetime | None:
        """When the current token dies, or None if there is no token yet."""
        return self._token.expires_at if self._token else None

    def forget(self) -> None:
        """Drop the cached token so the next call authenticates from scratch."""
        self._token = None

    async def refresh_now(self) -> None:
        """Force a refresh of the current token. Used to exercise the refresh path."""
        async with self._lock:
            if self._token is None:
                raise AuthError("Nothing to refresh: not authenticated yet")
            self._token = await self._refresh(self._token)

    async def _login(self) -> Token:
        payload = {
            "username": self._settings.username,
            "password": self._settings.password,
            "tzoffset": self._settings.tz_offset_hours(),
        }
        token = await self._post(payload, action="login")
        logger.info("Logged in to Comunio")
        return token

    async def _refresh(self, token: Token) -> Token:
        response = await self._post(
            {"refresh_token": token.refresh_token},
            action="refresh",
            headers={"authorization": f"Bearer {token.access_token}"},
        )
        logger.info("Refreshed the Comunio access token")
        return response

    async def _post(
        self, payload: dict, *, action: str, headers: dict[str, str] | None = None
    ) -> Token:
        try:
            response = await self._http.post(LOGIN_URL, json=payload, headers=headers)
        except httpx2.HTTPError as exc:
            raise AuthError(f"Comunio {action} request failed: {exc}") from exc

        if response.status_code >= 400:
            # The body may echo credentials back; only the status is safe to surface.
            raise AuthError(f"Comunio rejected the {action} with HTTP {response.status_code}")

        return Token.from_payload(response.json())
