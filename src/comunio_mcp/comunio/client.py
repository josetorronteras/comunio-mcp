"""HTTP client for api.comunio.es.

Tools call this and never see a token. Authentication is applied here and a stale
token is retried once, transparently.
"""

import logging
from typing import Any

import httpx2

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.config import Settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.comunio.es"
ORIGIN = "https://www.comunio.es"

# Copied verbatim from the web app's own traffic. The only request we know Comunio
# accepts is that one, so we reproduce it rather than sending a tidier subset: this is
# a private backend and anything in front of it may well be inspecting these.
# `user-agent` and `x-timezone` are filled in from settings.
BROWSER_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "es-ES,es;q=0.7",
    "content-type": "application/json",
    "origin": ORIGIN,
    "priority": "u=1, i",
    "referer": f"{ORIGIN}/",
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Brave";v="150"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "sec-gpc": "1",
}


def default_headers(settings: Settings) -> dict[str, str]:
    return {
        **BROWSER_HEADERS,
        "user-agent": settings.user_agent,
        "x-timezone": settings.timezone,
    }


class ComunioClient:
    def __init__(self, http: httpx2.AsyncClient, auth: ComunioAuth) -> None:
        self._http = http
        self._auth = auth

    async def get(self, target: str, **kwargs: Any) -> Any:
        """GET a JSON endpoint and return the decoded body.

        Accepts a path or a full URL, because the links in Comunio's index are absolute.
        """
        response = await self._request("GET", target, **kwargs)
        return response.json()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        response = await self._send(method, path, **kwargs)

        if response.status_code == 401:
            # The token died earlier than its `expires_in` promised. Drop it and give
            # the request one more go with a fresh one.
            logger.info("Got 401 from Comunio, re-authenticating and retrying once")
            self._auth.forget()
            response = await self._send(method, path, **kwargs)

        response.raise_for_status()
        return response

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        token = await self._auth.access_token()
        headers = {**kwargs.pop("headers", {}), "authorization": f"Bearer {token}"}
        return await self._http.request(method, _absolute(path), headers=headers, **kwargs)


def _absolute(target: str) -> str:
    return target if target.startswith("http") else f"{BASE_URL}{target}"
