"""Models for what Comunio returns.

These are **allowlists, not filters**. Only declared fields survive validation, so a
field Comunio adds tomorrow is dropped by default rather than leaking into the model's
context. That matters: the raw index response carries the account email, an invitation
code and Google identifiers, none of which belong in a conversation transcript.

Numbers arrive from the API as strings (`"20000000"`); Pydantic coerces them.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field


def _empty_to_none(value: Any) -> Any:
    """Comunio writes "no limit" as an empty string rather than null."""
    return None if value == "" else value


def _missing_to_none(value: Any) -> Any:
    """Comunio writes "no data yet" as a dash, and "not set" as an empty string."""
    return None if value in ("", "-") else value


def _sentinel_to_none(value: Any) -> Any:
    """`recommendedprice` is -1 when Comunio has no recommendation to give."""
    return None if value == -1 else value


OptionalInt = Annotated[int | None, BeforeValidator(_empty_to_none)]
#: A number that may arrive as a string, a dash, an empty string or null.
MissingInt = Annotated[int | None, BeforeValidator(_missing_to_none)]
MissingFloat = Annotated[float | None, BeforeValidator(_missing_to_none)]
MissingStr = Annotated[str | None, BeforeValidator(_missing_to_none)]
SentinelInt = Annotated[int | None, BeforeValidator(_sentinel_to_none)]


class CommunityRules(BaseModel):
    """The subset of community rules that constrains what moves are legal.

    Rules are league-wide rather than personal, but they are exactly what the
    deterministic layer needs: they decide what a valid bid or sale even looks like.
    """

    second_highest_offers: bool = Field(
        description="If true, a winning bid pays the second-highest offer instead of its own"
    )
    anonymous_bidding: bool = Field(description="If true, rival bids are hidden")
    salaries: bool = Field(description="Whether player salaries apply in this league")
    members: int = Field(description="Number of managers in the league")
    tradables_on_exchangemarket: int = Field(description="How many players the market holds")
    max_tradables_per_user: OptionalInt = Field(
        default=None, description="Cap on players one manager may list for sale, null if unlimited"
    )
    max_days_offers_are_pending: int = Field(
        description="Days an offer stays open before expiring, 0 for the league default"
    )
    sales_ban: int = Field(description="Sales ban in effect, 0 when selling is allowed")
    sales_ban_pro_offers: int = Field(description="Sales ban for offers from the computer")
    players_member_per_club: int = Field(
        description="Cap on players one manager may hold from the same club, 0 for no cap"
    )
    injured_tradable_offer_factor: float = Field(
        description="Price adjustment applied to injured players"
    )
    creditfactor: str = Field(description="How available credit is computed, e.g. 'dynamic'")
    buyout_clause: bool = Field(description="Whether buyout clauses are enabled")
    buyout_clause_factor: float = Field(description="Multiplier applied to a buyout clause")
    buyout_clause_trade_lock: int = Field(description="Trade lock after paying a buyout clause")
    public_transaction_values: bool = Field(
        description="Whether the prices other managers paid are visible"
    )


class Community(BaseModel):
    id: str = Field(description="League identifier used in API routes")
    name: str = Field(description="League name")
    rules: CommunityRules = Field(description="Rules that constrain legal moves")


class Account(BaseModel):
    """The signed-in manager. Personal identity beyond the display name is left out."""

    id: str = Field(description="Manager identifier used in API routes")
    name: str = Field(description="Manager display name, as shown in the standings")
    budget: int = Field(description="Cash available to spend, in euros")
    # Comunio sends camelCase; we read it but expose snake_case, so the payload the
    # model sees is consistent with every other field.
    team_value: int = Field(
        validation_alias="teamValue", description="Total value of the squad, in euros"
    )
    team_count: int = Field(
        validation_alias="teamCount", description="Players currently in the squad"
    )
    team_count_linedup: int = Field(
        validation_alias="teamCountLinedup", description="Players currently in the starting lineup"
    )
    points: int = Field(description="Points accumulated this season")
    salaries: int = Field(description="Salaries currently payable, in euros")
    tactic: str = Field(description="Current formation, e.g. '442'")

    model_config = {"populate_by_name": True}


class AccountSnapshot(BaseModel):
    """Everything the index endpoint tells us that is worth knowing.

    A snapshot in time: budget and squad value move constantly, so this is never cached.
    """

    account: Account
    community: Community


class Club(BaseModel):
    id: int = Field(description="Club identifier")
    name: str = Field(description="Club name")


class NextMatch(BaseModel):
    """The player's next fixture. Null when none is scheduled yet."""

    home: str = Field(description="Home club")
    away: str = Field(description="Away club")
    kickoff: datetime = Field(description="Kick-off time, with timezone")


class SquadPlayer(BaseModel):
    id: int = Field(description="Player identifier, used to bid or to look up history")
    name: str = Field(description="Player name")
    club: Club
    position: str = Field(description="keeper, defender, midfielder or striker")

    # Availability
    status: str = Field(description="ACTIVE, or WEAKENED and similar when unavailable")
    status_info: MissingStr = Field(
        default=None,
        validation_alias="statusInfo",
        description="Why the player is unavailable, e.g. an injury description",
    )
    next_match: NextMatch | None = Field(
        default=None, validation_alias="nextMatch", description="Next fixture, if scheduled"
    )

    # Scoring
    points: MissingInt = Field(default=None, description="Season points, null before any")
    last_points: MissingInt = Field(
        default=None, validation_alias="lastPoints", description="Points in the last matchday"
    )
    average_points: MissingFloat = Field(
        default=None, validation_alias="averagePoints", description="Average points per matchday"
    )
    matchday_points: MissingInt = Field(
        default=None,
        validation_alias="matchdayPoints",
        description="Points in the current matchday",
    )
    motm: bool = Field(description="Was man of the match")

    # Lineup
    linedup: bool = Field(description="Currently in the starting eleven")
    substitute: bool = Field(description="Currently named as a substitute")
    lineup_slot: MissingStr = Field(
        default=None,
        validation_alias="pos",
        description="Slot in the formation, set only when lined up",
    )

    # Market
    quoted_price: int = Field(
        validation_alias="quotedprice", description="Current market value, in euros"
    )
    recommended_price: SentinelInt = Field(
        default=None,
        validation_alias="recommendedprice",
        description="Comunio's suggested asking price, null when it has none",
    )
    on_market: bool = Field(
        validation_alias="onMarket", description="Listed for sale by its owner"
    )
    is_exchangeable: bool = Field(
        validation_alias="isExchangeable", description="Whether it can be traded right now"
    )
    has_accepted_offers: bool = Field(
        validation_alias="hasAcceptedOffers", description="An offer for this player was accepted"
    )
    watched: bool = Field(description="On the manager's watchlist")

    model_config = {"populate_by_name": True}


class SquadSummary(BaseModel):
    """Counts the lineup rules are checked against, so nobody has to recount them."""

    total: int = Field(description="Players in the squad")
    lined_up: int = Field(description="Players in the starting eleven")
    substitutes: int = Field(description="Players named as substitutes")
    unavailable: int = Field(description="Players whose status is not ACTIVE")
    on_market: int = Field(description="Players currently listed for sale")
    by_position: dict[str, int] = Field(description="How many players per position")


class Squad(BaseModel):
    owner: str | None = Field(default=None, description="Manager the squad belongs to")
    tactic: str = Field(description="Formation the lineup is set up for, e.g. '442'")
    summary: SquadSummary
    players: list[SquadPlayer]
