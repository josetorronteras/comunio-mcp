"""Check real credentials against api.comunio.es.

Run it with `docker compose run --rm auth-check`. It exercises login and refresh and
reports how long the tokens last. It never prints a token.
"""

import asyncio
import logging
import sys
from datetime import UTC, datetime

import httpx2

from comunio_mcp.comunio.auth import AuthError, ComunioAuth
from comunio_mcp.comunio.client import default_headers
from comunio_mcp.config import ConfigError, Settings


async def _run() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"Timezone {settings.timezone}, tzoffset {settings.tz_offset_hours()}")

    async with httpx2.AsyncClient(headers=default_headers(settings), timeout=15.0) as http:
        auth = ComunioAuth(http, settings)

        try:
            await auth.access_token()
        except AuthError as exc:
            print(f"Login failed: {exc}", file=sys.stderr)
            return 1
        print("Login OK")

        try:
            await auth.refresh_now()
        except AuthError as exc:
            print(f"Refresh failed: {exc}", file=sys.stderr)
            return 1
        print("Refresh OK")

        expires_at = auth.expires_at
        if expires_at is not None:
            seconds_left = int((expires_at - datetime.now(UTC)).total_seconds())
            print(f"Access token valid for another {seconds_left}s")

    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s: %(message)s")
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
