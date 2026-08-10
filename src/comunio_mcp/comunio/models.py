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


class StandingsRow(BaseModel):
    """One manager in the league table.

    Third-party data is kept to what a standings table needs: a display name, the figures,
    and the id required to look up their squad. Login, real name and account flags are
    dropped.
    """

    rank: int = Field(description="Position in the table, 1 is top")
    is_me: bool = Field(description="True for the signed-in manager's own row")
    manager_id: int = Field(description="Manager identifier, used to fetch their squad")
    manager: str = Field(description="Manager display name")
    total_points: int = Field(description="Points this season")
    last_points: MissingInt = Field(default=None, description="Points in the last matchday")
    live_points: MissingInt = Field(
        default=None, description="Points being scored right now, null outside a matchday"
    )
    perennial_points: int = Field(description="Points carried across seasons")
    players_possibly_scoring: int = Field(
        description="Players of theirs who may still score in the current matchday"
    )
    team_value: int = Field(description="Value of their squad, in euros")
    negative_budget: bool = Field(
        description="Their budget is in the red, so they cannot outbid anyone"
    )


class Standings(BaseModel):
    period: str = Field(description="Period the table covers, e.g. 'total'")
    rows: list[StandingsRow] = Field(description="Managers, best first")


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


class MarketListing(BaseModel):
    """One player up for sale.

    Note the capitalisation: this endpoint sends `quotedPrice`, while the squad endpoint
    sends `quotedprice` for the same concept. The aliases are not interchangeable.
    """

    player_id: int = Field(validation_alias="id", description="Player identifier, used to bid")
    name: str = Field(description="Player name")
    club: Club
    position: str = Field(description="keeper, defender, midfielder or striker")

    status: str = Field(description="ACTIVE, or WEAKENED and similar when unavailable")
    status_info: MissingStr = Field(
        default=None, validation_alias="statusInfo", description="Why the player is unavailable"
    )
    points: MissingInt = Field(default=None, description="Season points, null before any")

    quoted_price: int = Field(
        validation_alias="quotedPrice", description="Current market value, in euros"
    )
    recommended_price: SentinelInt = Field(
        default=None,
        validation_alias="recommendedPrice",
        description="Comunio's suggested price, null when it has none",
    )
    trend: int = Field(description="Price movement, negative when falling")

    seller: str = Field(description="Who is selling")
    seller_id: int = Field(description="Seller identifier")
    from_computer: bool = Field(
        description="Listed by Comunio itself rather than by a manager, so nobody is negotiating"
    )
    is_mine: bool = Field(description="One of the signed-in manager's own listings")

    listed_at: datetime = Field(description="When the listing appeared")
    remaining: int = Field(description="Comunio's countdown on the listing")
    watched: bool = Field(description="On the manager's watchlist")

    model_config = {"populate_by_name": True}


class MarketSummary(BaseModel):
    total: int = Field(description="Players on the market")
    from_computer: int = Field(description="Listed by Comunio itself")
    from_managers: int = Field(description="Listed by managers, the signed-in one included")
    mine: int = Field(description="The signed-in manager's own listings")
    unavailable: int = Field(description="Listed players whose status is not ACTIVE")
    by_position: dict[str, int] = Field(description="How many listings per position")


class Market(BaseModel):
    closes_at: datetime | None = Field(
        default=None,
        description="When the current round of transfers is processed. Bids must be in by then.",
    )
    daily_transfers_processed: bool = Field(
        description="Whether today's transfer round has already run"
    )
    summary: MarketSummary
    listings: list[MarketListing]


class OfferPlayer(BaseModel):
    """The player an offer is about. A leaner view than the market's."""

    id: int = Field(description="Player identifier")
    name: str = Field(description="Player name")
    club: Club
    position: str = Field(description="keeper, defender, midfielder or striker")
    status: str = Field(description="ACTIVE, or WEAKENED and similar when unavailable")
    status_info: MissingStr = Field(
        default=None, validation_alias="statusInfo", description="Why the player is unavailable"
    )
    quoted_price: int = Field(
        validation_alias="quotedPrice", description="Current market value, in euros"
    )
    recommended_price: SentinelInt = Field(
        default=None, validation_alias="recommendedPrice", description="Comunio's suggested price"
    )
    trend: int = Field(description="Price movement, negative when falling")

    model_config = {"populate_by_name": True}


class Offer(BaseModel):
    offer_id: int = Field(description="Offer identifier, needed to accept, decline or withdraw")
    type: str = Field(description="What kind of trade, e.g. SALE")
    state: str = Field(description="Where the offer stands, e.g. PENDING")
    direction: str = Field(
        description="'incoming' when somebody wants the manager's player, 'outgoing' when the "
        "manager is bidding for someone else's"
    )

    player: OfferPlayer
    price: int = Field(description="Amount offered, in euros")
    premium: int = Field(
        description="Offer minus the player's quoted price. Negative means below market value."
    )
    premium_pct: float = Field(description="The same difference as a percentage of quoted price")

    offered_by: str = Field(description="Who made the offer")
    offered_by_id: int = Field(description="Identifier of who made the offer")
    from_computer: bool = Field(description="The offer comes from Comunio itself, not a manager")
    counterparty: str = Field(description="The manager on the other side of the offer")

    is_exchange: bool = Field(
        validation_alias="exchange", description="Whether players are being swapped as well"
    )
    created_at: datetime = Field(description="When the offer was made")
    changed_at: datetime = Field(description="When it was last modified")

    model_config = {"populate_by_name": True}


class OffersSummary(BaseModel):
    total: int = Field(description="Offers open right now")
    incoming: int = Field(description="Offers for the manager's own players")
    outgoing: int = Field(description="Offers the manager has made")
    from_computer: int = Field(description="Offers made by Comunio itself")
    below_quoted: int = Field(description="Incoming offers below the player's market value")
    incoming_total: int = Field(
        description="What accepting every incoming offer would bring in, in euros"
    )


class Offers(BaseModel):
    credit: int = Field(
        description="What the manager can actually spend. Not the same as budget: the league's "
        "credit factor lets it exceed cash in hand."
    )
    has_more: bool = Field(description="Whether Comunio is holding back further pages")
    summary: OffersSummary
    offers: list[Offer]


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
