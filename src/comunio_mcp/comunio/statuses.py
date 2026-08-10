"""What Comunio's player status codes mean.

The API sends bare codes and nothing else, so an agent seeing `YELLOW_RED_BANNED` has to
guess. The full vocabulary was recovered from the web app's own translation table, which
lists thirteen values where the API had only shown four.

`WAS_*` variants describe a state the player has come out of. They are handled by prefix
rather than listed twice.

This is a lookup, not a validator: `status` stays a plain string everywhere, and an
unrecognised code passes through untranslated rather than failing.
"""

WAS_PREFIX = "WAS_"

MEANINGS = {
    "ACTIVE": "available",
    "AWAY": "away on international duty",
    "DECEASED": "deceased",
    "GAME_BREAK": "on a break",
    "INJURED": "injured",
    "MISCELLANEOUS": "unavailable for other reasons",
    "RED_BANNED": "suspended after a straight red",
    "REHABILITATION": "in rehabilitation",
    "RETIRED": "has left the league",
    "SUSPENDED": "left out of the squad",
    "WEAKENED": "carrying a knock",
    "YELLOW_BANNED": "suspended for accumulated yellows",
    "YELLOW_RED_BANNED": "suspended after a second yellow",
}

#: Everything that is not this means the player cannot be counted on.
AVAILABLE = "ACTIVE"


def meaning(status: str | None) -> str | None:
    """Plain-language reading of a status code, or None if it is unknown."""
    if not status:
        return None

    if status.startswith(WAS_PREFIX):
        past = MEANINGS.get(status[len(WAS_PREFIX) :])
        return f"was {past}" if past else None

    return MEANINGS.get(status)
