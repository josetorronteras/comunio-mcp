from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from comunio_mcp.config import DEFAULT_TIMEZONE, DEFAULT_USER_AGENT, ConfigError, Settings


def test_from_env_reads_credentials(monkeypatch):
    monkeypatch.setenv("COMUNIO_USERNAME", "manager")
    monkeypatch.setenv("COMUNIO_PASSWORD", "s3cret")
    monkeypatch.delenv("COMUNIO_TIMEZONE", raising=False)
    monkeypatch.delenv("COMUNIO_USER_AGENT", raising=False)

    settings = Settings.from_env()

    assert settings.username == "manager"
    assert settings.password == "s3cret"
    assert settings.timezone == DEFAULT_TIMEZONE
    assert settings.user_agent == DEFAULT_USER_AGENT


@pytest.mark.parametrize(
    ("username", "password"),
    [("", "s3cret"), ("manager", ""), ("", "")],
)
def test_missing_credentials_is_a_config_error(monkeypatch, username, password):
    monkeypatch.setenv("COMUNIO_USERNAME", username)
    monkeypatch.setenv("COMUNIO_PASSWORD", password)

    with pytest.raises(ConfigError):
        Settings.from_env()


def test_invalid_timezone_is_a_config_error(monkeypatch):
    monkeypatch.setenv("COMUNIO_USERNAME", "manager")
    monkeypatch.setenv("COMUNIO_PASSWORD", "s3cret")
    monkeypatch.setenv("COMUNIO_TIMEZONE", "Mars/Olympus_Mons")

    with pytest.raises(ConfigError):
        Settings.from_env()


def test_tz_offset_follows_daylight_saving():
    settings = Settings(username="m", password="p", timezone="Europe/Madrid")
    madrid = ZoneInfo("Europe/Madrid")

    summer = datetime(2026, 7, 1, 12, 0, tzinfo=madrid)
    winter = datetime(2026, 1, 1, 12, 0, tzinfo=madrid)

    assert settings.tz_offset_hours(summer) == 2
    assert settings.tz_offset_hours(winter) == 1
