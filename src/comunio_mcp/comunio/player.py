"""A single player's detail sheet: `game:tradable`.

This is the `detailedInfo` link that the squad and market responses hang off every player.
It is the API route for player detail — the one the web app's own player page uses is a
Next.js `_next/data` URL containing a build id that changes on every deploy, wrapped in
several thousand UI translation strings. This is 4 KB of data with the same Bearer token
as everything else.

Two things it has that nothing else does: **points season by season**, and the
**buyout clause price** — what taking the player from their owner without consent would
cost.
"""

from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import (
    BuyoutClause,
    Club,
    PlayerAverages,
    PlayerDetail,
    PlayerProfile,
    PlayerRecord,
    SeasonPoints,
    UpcomingMatch,
)
from comunio_mcp.comunio.session import Session
from comunio_mcp.comunio.statuses import AVAILABLE, meaning

PLAYER_LINK = "game:tradable"

#: Comunio dates a player who was never bought — one from the initial draft — to the Unix
#: epoch. Read literally it says the manager signed them in 1970.
EPOCH = "1970-01-01"


def _real_date(value: Any) -> str | None:
    """A date, unless it is the epoch standing in for "never"."""
    if not value or str(value).startswith(EPOCH):
        return None
    return str(value)


def _real_number(value: Any) -> int | None:
    """A number, unless it is a zero standing in for "not applicable"."""
    return None if not value else value


async def fetch_player(session: Session, client: ComunioClient, player_id: int) -> PlayerDetail:
    url = await session.link(PLAYER_LINK, playerId=str(player_id))
    return parse_player(await client.get(url))


def parse_player(payload: Any) -> PlayerDetail:
    status = payload.get("status", "")
    general = payload.get("general") or {}
    cards = payload.get("cards") or {}
    averages = payload.get("average") or {}
    recent = averages.get("lastXMatchdays") or {}
    clause = payload.get("buyoutClauseInfo") or {}
    purchase = payload.get("purchaseInfo") or {}
    club = payload.get("club") or {}
    owner = payload.get("owner") or {}
    extended = payload.get("extendedInfo") or {}

    return PlayerDetail(
        player_id=payload.get("playerId"),
        name=payload.get("name", ""),
        club=Club(id=club.get("id", 0), name=club.get("name", "")),
        price=payload.get("price", 0),
        status=status,
        status_meaning=meaning(status),
        status_info=payload.get("statusInfo"),
        available=status == AVAILABLE,
        total_points=payload.get("totalPoints"),
        last_points=payload.get("lastPoints"),
        averages=PlayerAverages(
            grade=averages.get("grade"),
            points=averages.get("points"),
            recent_matches=recent.get("matchesAmount"),
            recent_grade=recent.get("grade"),
            recent_points=recent.get("points"),
        ),
        record=PlayerRecord(
            played=general.get("playedGames", 0),
            rated=general.get("ratedGames", 0),
            goals=general.get("totalGoals", 0),
            penalties=general.get("totalPenalties", 0),
            man_of_the_match=general.get("manOfTheMatchAmount", 0),
            yellow_cards=cards.get("yellow", 0),
            yellow_red_cards=cards.get("yellowRed", 0),
            red_cards=cards.get("red", 0),
        ),
        history=_parse_history(payload.get("historical") or {}),
        owner=(owner.get("name") or "").strip() or None,
        owner_id=owner.get("id"),
        purchase_price=_real_number(purchase.get("price")),
        purchased_on=_real_date(purchase.get("date")),
        buyout_clause=BuyoutClause(
            # Zero means the league has clauses disabled, not that one is free. Left as a
            # number it invites exactly that arithmetic.
            price=_real_number(clause.get("price")),
            paid=bool(clause.get("paid")),
            available_from=clause.get("dateOfAvailability"),
            block_days=_real_number(clause.get("blockDays")),
        ),
        watched=bool(payload.get("watched")),
        next_matches=_parse_matches(payload.get("nextMatches") or []),
        profile=PlayerProfile(
            # A date of birth arrives as a full timestamp with a made-up time on it.
            date_of_birth=(_real_date(extended.get("dob")) or "")[:10] or None,
            nationality=extended.get("nationality"),
            height=extended.get("height"),
            weight=extended.get("weight"),
            preferred_foot=extended.get("preferredFoot"),
            shirt_number=_real_number(extended.get("jerseyNumber")),
        ),
    )


def _parse_history(historical: dict) -> list[SeasonPoints]:
    return [
        SeasonPoints(season=entry.get("season", ""), points=entry.get("points"))
        for entry in (historical.get("points") or [])
    ]


def _parse_matches(matches: list) -> list[UpcomingMatch]:
    return [
        UpcomingMatch(
            matchday=match.get("matchdayNr"),
            home=(match.get("homeClub") or {}).get("name", ""),
            away=(match.get("guestClub") or {}).get("name", ""),
            kickoff=match["kickoff"],
        )
        for match in matches
        if match.get("kickoff")
    ]
