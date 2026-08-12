"""Configuration read from the environment.

Credentials never live in the image or in git: the MCP client passes them to the
container as environment variables. See docs/setup.md.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Madrid"

# The user agent from the captured web-app traffic. Kept as-is because the request we
# know Comunio accepts carried exactly this; override with COMUNIO_USER_AGENT.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"
)


class ConfigError(RuntimeError):
    """Something required is missing or malformed in the environment."""


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    timezone: str = DEFAULT_TIMEZONE
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_env(cls) -> "Settings":
        username = os.environ.get("COMUNIO_USERNAME", "").strip()
        password = os.environ.get("COMUNIO_PASSWORD", "")
        if not username or not password:
            raise ConfigError(
                "COMUNIO_USERNAME and COMUNIO_PASSWORD must be set. "
                "Pass them to the container with -e; see docs/setup.md."
            )

        timezone = os.environ.get("COMUNIO_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        try:
            ZoneInfo(timezone)
        except Exception as exc:
            raise ConfigError(
                f"COMUNIO_TIMEZONE is not a valid IANA timezone: {timezone!r}"
            ) from exc

        user_agent = os.environ.get("COMUNIO_USER_AGENT", "").strip() or DEFAULT_USER_AGENT

        return cls(
            username=username,
            password=password,
            timezone=timezone,
            user_agent=user_agent,
        )

    def tz_offset_hours(self, now: datetime | None = None) -> int:
        """UTC offset the API expects as `tzoffset` on login.

        Computed rather than hardcoded: Madrid is +2 in summer and +1 in winter, and a
        stale constant would quietly start lying at the next DST change.
        """
        moment = now or datetime.now(ZoneInfo(self.timezone))
        offset = moment.astimezone(ZoneInfo(self.timezone)).utcoffset()
        assert offset is not None  # a zoneinfo-aware datetime always has one
        return int(offset.total_seconds() // 3600)
