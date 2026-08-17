"""Models for what Comunio returns.

These are **allowlists, not filters**. Only declared fields survive validation, so a
field Comunio adds tomorrow is dropped by default rather than leaking into the model's
context. That matters: the raw index response carries the account email, an invitation
code and Google identifiers, none of which belong in a conversation transcript.

Numbers arrive from the API as strings (`"20000000"`); Pydantic coerces them.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class ComunioModel(BaseModel):
    """Base for everything Comunio returns.

    Comunio spells its fields differently from this server, so fields carry a
    `validation_alias`. Pydantic puts those aliases into the JSON schema, while
    `model_dump()` emits the field names — the declared output schema then disagrees
    with every response, and a client that validates structured output rejects all of
    them. Generating the schema by field name keeps the two in step.

    `by_alias` is taken positionally as well as by keyword, because the caller is the
    MCP framework rather than this code.
    """

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def model_json_schema(cls, by_alias: bool = True, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("by_alias", None)
        return super().model_json_schema(False, *args, **kwargs)


def _empty_to_none(value: Any) -> Any:
    """Comunio writes "no limit" as an empty string rather than null."""
    return None if value == "" else value


def _missing_to_none(value: Any) -> Any:
    """Comunio writes "no data yet" as a dash, and "not set" as an empty string."""
    return None if value in ("", "-") else value


def _decimal_comma(value: Any) -> Any:
    """Comunio writes decimals with a Spanish comma once matches have been played.

    In pre-season every grade is a plain `0`, so this only shows up after the first
    matchday: `"6,9"` reaches a float field and parsing fails.
    """
    if value in ("", "-"):
        return None
    if isinstance(value, str):
        return value.replace(",", ".")
    return value


def _sentinel_to_none(value: Any) -> Any:
    """`recommendedprice` is -1 when Comunio has no recommendation to give."""
    return None if value == -1 else value


OptionalInt = Annotated[int | None, BeforeValidator(_empty_to_none)]
#: A number that may arrive as a string, a dash, an empty string or null.
MissingInt = Annotated[int | None, BeforeValidator(_missing_to_none)]
MissingFloat = Annotated[float | None, BeforeValidator(_decimal_comma)]
MissingStr = Annotated[str | None, BeforeValidator(_missing_to_none)]
SentinelInt = Annotated[int | None, BeforeValidator(_sentinel_to_none)]


class CommunityRules(ComunioModel):
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


class Community(ComunioModel):
    id: str = Field(description="League identifier used in API routes")
    name: str = Field(description="League name")
    rules: CommunityRules = Field(description="Rules that constrain legal moves")


class Account(ComunioModel):
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



class AccountSnapshot(ComunioModel):
    """Everything the index endpoint tells us that is worth knowing.

    A snapshot in time: budget and squad value move constantly, so this is never cached.
    """

    account: Account
    community: Community


class StandingsRow(ComunioModel):
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


class Standings(ComunioModel):
    period: str = Field(description="Period the table covers, e.g. 'total'")
    rows: list[StandingsRow] = Field(description="Managers, best first")


class Club(ComunioModel):
    id: int = Field(description="Club identifier")
    name: str = Field(description="Club name")


class NextMatch(ComunioModel):
    """The player's next fixture. Null when none is scheduled yet."""

    home: str = Field(description="Home club")
    away: str = Field(description="Away club")
    kickoff: datetime = Field(description="Kick-off time, with timezone")


class SquadPlayer(ComunioModel):
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



class MarketListing(ComunioModel):
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



class MarketSummary(ComunioModel):
    total: int = Field(description="Players on the market")
    from_computer: int = Field(description="Listed by Comunio itself")
    from_managers: int = Field(description="Listed by managers, the signed-in one included")
    mine: int = Field(description="The signed-in manager's own listings")
    unavailable: int = Field(description="Listed players whose status is not ACTIVE")
    by_position: dict[str, int] = Field(description="How many listings per position")


class Market(ComunioModel):
    closes_at: datetime | None = Field(
        default=None,
        description="When the current round of transfers is processed. Bids must be in by then.",
    )
    daily_transfers_processed: bool = Field(
        description="Whether today's transfer round has already run"
    )
    summary: MarketSummary
    listings: list[MarketListing]


class OfferPlayer(ComunioModel):
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



class Offer(ComunioModel):
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



class OffersSummary(ComunioModel):
    total: int = Field(description="Offers open right now")
    incoming: int = Field(description="Offers for the manager's own players")
    outgoing: int = Field(description="Offers the manager has made")
    from_computer: int = Field(description="Offers made by Comunio itself")
    below_quoted: int = Field(description="Incoming offers below the player's market value")
    incoming_total: int = Field(
        description="What accepting every incoming offer would bring in, in euros"
    )


class Offers(ComunioModel):
    credit: int = Field(
        description="What the manager can actually spend. Not the same as budget: the league's "
        "credit factor lets it exceed cash in hand."
    )
    has_more: bool = Field(description="Whether Comunio is holding back further pages")
    summary: OffersSummary
    offers: list[Offer]


class Transfer(ComunioModel):
    """A completed transfer. What a player actually changed hands for."""

    offer_id: int = Field(description="Identifier of the offer that settled into this")
    player_id: int = Field(description="Player identifier")
    player: str = Field(description="Player name")
    club: MissingStr = Field(default=None, description="The player's club")
    position: MissingStr = Field(
        default=None, description="keeper, defender, midfielder or striker"
    )
    status: MissingStr = Field(
        default=None, description="The player's availability when the deal settled"
    )

    price: int = Field(description="What was actually paid, in euros")
    quoted_price: MissingInt = Field(
        default=None,
        description="What the player was valued at, for comparison with what was paid",
    )

    from_manager: str = Field(description="Who the player came from")
    from_id: int = Field(description="Identifier of the seller")
    to_manager: str = Field(description="Who the player went to")
    to_id: int = Field(description="Identifier of the buyer")

    from_computer: bool = Field(description="Bought from Comunio itself")
    to_computer: bool = Field(description="Sold back to Comunio itself")
    involves_me: bool = Field(description="The signed-in manager was on one side of it")

    offered_at: datetime = Field(description="When the offer was made")
    settled_at: datetime = Field(description="When it went through")


class TransfersSummary(ComunioModel):
    total: int = Field(description="Transfers returned")
    bought_from_computer: int = Field(description="Players bought from Comunio")
    sold_to_computer: int = Field(description="Players sold back to Comunio")
    between_managers: int = Field(description="Transfers between two managers")
    mine: int = Field(description="Transfers the signed-in manager was part of")
    total_value: int = Field(description="Everything added up, in euros")


class Transfers(ComunioModel):
    summary: TransfersSummary
    has_more: bool = Field(description="Whether older transfers exist beyond what was fetched")
    transfers: list[Transfer] = Field(description="Newest first")


class NewsLink(ComunioModel):
    """A link inside an announcement body."""

    text: str = Field(description="The anchor text as it reads in the announcement")
    url: str = Field(description="Where it points")


class NewsEntry(ComunioModel):
    """One item in the league feed, reduced to what it says.

    The feed carries several kinds of entry under one shape, so the type-specific fields
    are null on the kinds they do not apply to.
    """

    id: int = Field(description="Entry identifier")
    date: datetime = Field(description="When it was posted")
    edited_at: MissingStr = Field(
        default=None, description="When it was last edited, null if never"
    )
    type: str = Field(
        description="What kind of entry it is: TRANSACTION_TRANSFER, LINEUP_CHANGED, "
        "SYSTEM_ADMINISTRATION, COMMUNITY_ADMINISTRATION, MEMBER_ADMINISTRATION. An open "
        "set — Comunio may send others"
    )
    title: str = Field(
        description="Headline. On administration entries this is the whole announcement, "
        "with an empty body"
    )
    text: MissingStr = Field(
        default=None,
        description="Body as plain text, with Comunio's HTML and entities stripped. Null "
        "when the entry has no body",
    )
    links: list[NewsLink] = Field(
        default_factory=list, description="Links the body pointed at, if any"
    )
    sticky: bool = Field(description="Pinned to the top of the feed")
    comments: int = Field(description="How many comments managers left on it")
    has_poll: bool = Field(description="Whether the entry carries a poll")

    tactic: MissingStr = Field(
        default=None, description="LINEUP_CHANGED only: the formation it was changed to"
    )
    lineup_incomplete: bool | None = Field(
        default=None,
        description="LINEUP_CHANGED only: whether slots were left empty, which costs points",
    )
    transfers: MissingInt = Field(
        default=None,
        description="TRANSACTION_TRANSFER only: how many moves it covers. Use get_transfers "
        "for the players, prices and sides",
    )


class NewsSummary(ComunioModel):
    total: int = Field(description="Entries returned")
    by_type: dict[str, int] = Field(description="How many of each type came back")


class News(ComunioModel):
    summary: NewsSummary
    has_more: bool = Field(description="Whether older entries exist beyond what was fetched")
    entries: list[NewsEntry] = Field(description="Newest first")


class PlayerRecord(ComunioModel):
    """Career totals for the current season."""

    played: int = Field(description="Matches played")
    rated: int = Field(description="Matches Comunio graded")
    goals: int = Field(description="Goals scored")
    penalties: int = Field(description="Penalties scored")
    man_of_the_match: int = Field(description="Times named man of the match")
    yellow_cards: int = Field(description="Yellow cards")
    yellow_red_cards: int = Field(description="Second-yellow dismissals")
    red_cards: int = Field(description="Straight reds")


class PlayerAverages(ComunioModel):
    grade: MissingFloat = Field(default=None, description="Average grade this season")
    points: MissingFloat = Field(default=None, description="Average Comunio points per match")
    recent_matches: MissingInt = Field(
        default=None, description="How many matches the recent averages cover"
    )
    recent_grade: MissingFloat = Field(default=None, description="Average grade over those matches")
    recent_points: MissingFloat = Field(
        default=None, description="Average points over those matches"
    )


class PlayerProfile(ComunioModel):
    """Biography. Rarely decisive, but cheap and occasionally the tiebreaker."""

    date_of_birth: MissingStr = Field(default=None, description="Date of birth")
    nationality: MissingStr = Field(default=None, description="Nationality")
    height: MissingInt = Field(default=None, description="Height in centimetres")
    weight: MissingInt = Field(default=None, description="Weight in kilograms")
    preferred_foot: MissingStr = Field(default=None, description="Preferred foot")
    shirt_number: MissingInt = Field(default=None, description="Shirt number")


class SeasonPoints(ComunioModel):
    season: str = Field(description="Season, e.g. '25/26'")
    points: MissingInt = Field(default=None, description="Points scored that season")


class BuyoutClause(ComunioModel):
    """The price at which a player can be taken from their owner without consent."""

    price: MissingInt = Field(
        default=None,
        description="What paying the clause would cost, or null when the league has clauses "
        "off. Never zero: a zero would read as free.",
    )
    paid: bool = Field(description="Whether somebody has already paid it")
    available_from: MissingStr = Field(
        default=None, description="When the clause becomes payable, if not yet"
    )
    block_days: MissingInt = Field(
        default=None, description="Days the player is trade-locked after a clause is paid"
    )


class UpcomingMatch(ComunioModel):
    matchday: MissingInt = Field(default=None, description="Matchday number")
    home: str = Field(description="Home club")
    away: str = Field(description="Away club")
    kickoff: datetime = Field(description="Kick-off time, with timezone")


class PlayerDetail(ComunioModel):
    player_id: int = Field(description="Player identifier")
    name: str = Field(description="Player name")
    club: Club
    price: int = Field(description="Current market value, in euros")

    status: str = Field(description="Availability code, e.g. ACTIVE or YELLOW_RED_BANNED")
    status_meaning: MissingStr = Field(
        default=None, description="Plain-language reading of the status code"
    )
    status_info: MissingStr = Field(default=None, description="Comunio's note on the status")
    available: bool = Field(description="Whether the player can be counted on right now")

    total_points: MissingInt = Field(default=None, description="Points this season")
    last_points: MissingInt = Field(default=None, description="Points in the last matchday")
    averages: PlayerAverages
    record: PlayerRecord
    history: list[SeasonPoints] = Field(
        description="Points season by season, oldest first, as Comunio orders them"
    )

    owner: MissingStr = Field(default=None, description="Manager who owns the player")
    owner_id: MissingInt = Field(default=None, description="That manager's identifier")
    purchase_price: MissingInt = Field(
        default=None, description="What the current owner paid, in euros"
    )
    purchased_on: MissingStr = Field(
        default=None,
        description="When the owner bought them, or null for a player from the initial "
        "draft who was never bought",
    )
    buyout_clause: BuyoutClause
    watched: bool = Field(description="On the signed-in manager's watchlist")

    next_matches: list[UpcomingMatch] = Field(description="Upcoming fixtures, soonest first")
    profile: PlayerProfile


class ListingResult(ComunioModel):
    """What actually happened when players were put on the market.

    `addplayer` is a batch endpoint, so partial success is normal: `placed` and `rejected`
    are read from the response rather than inferred from the outer `status`.
    """

    placed: list[int] = Field(description="Player ids that are now listed")
    rejected: list[int] = Field(description="Player ids Comunio refused to list")
    remaining: MissingInt = Field(
        default=None,
        description="Comunio's own counter from the response. What it counts is not "
        "documented and does not match the countdown on market listings.",
    )


class UnlistResult(ComunioModel):
    """What came back from taking players off the market.

    Unlike listing, this endpoint reports **no per-player detail** — just an overall
    status. So `unlisted` is what was asked for, not what Comunio confirmed. Check
    `get_market` if it matters.
    """

    ok: bool = Field(description="Whether Comunio reported the request as successful")
    unlisted: list[int] = Field(description="Player ids the request asked to take off sale")


class AskingPriceResult(ComunioModel):
    """What came back from changing a listed player's asking price.

    This endpoint answers with a bare `true`, not an object, so there is nothing to read
    beyond whether it worked.
    """

    ok: bool = Field(description="Whether Comunio accepted the change")
    player_id: int = Field(description="Player whose price was changed")
    price: int = Field(description="The asking price that was requested, in euros")


class WithdrawResult(ComunioModel):
    """What came back from withdrawing one of the manager's own bids."""

    ok: bool = Field(description="Whether Comunio accepted the withdrawal")
    offer_id: int = Field(description="The offer that was withdrawn")
    player: MissingStr = Field(default=None, description="Who the withdrawn bid was for")
    price: MissingInt = Field(default=None, description="What the withdrawn bid offered")


class BidResult(ComunioModel):
    """What actually happened to a bid.

    Read from the **per-item** status inside the response, never the outer one: Comunio
    can report overall success with the bid rejected inside.
    """

    ok: bool = Field(description="Whether this particular bid was accepted by Comunio")
    message: MissingStr = Field(default=None, description="Comunio's reason, when it gives one")
    offer_id: MissingInt = Field(
        default=None, description="The offer Comunio created. Needed to change or withdraw it."
    )
    player_id: int = Field(description="Player the bid is for")
    player: MissingStr = Field(default=None, description="That player's name")
    price: int = Field(description="Amount bid, in euros")
    applied_immediately: bool = Field(
        description="False for a bid: it waits for the transfer round and can be withdrawn"
    )
    credit_committed: MissingInt = Field(
        default=None,
        description="Already tied up in the manager's other open bids, in euros",
    )
    credit_after: MissingInt = Field(
        default=None,
        description="Spending power left if every open bid wins, in euros. Accounts for "
        "the other bids, which Comunio's own `credit` figure does not.",
    )


class AcceptResult(ComunioModel):
    """What happened when an offer for one of the manager's players was accepted.

    The only action in this project that cannot be undone. The player leaves the squad
    immediately and there is no withdrawal, no cancellation and no transfer round to wait
    through.
    """

    ok: bool = Field(description="Whether Comunio accepted this particular acceptance")
    message: MissingStr = Field(default=None, description="Comunio's reason, when it gives one")
    offer_id: int = Field(description="The offer that was accepted")
    player_id: int = Field(description="Player who has left the squad")
    player: MissingStr = Field(default=None, description="That player's name")
    price: int = Field(description="What was received for them, in euros")
    premium: int = Field(
        description="Price minus the player's quoted value. Negative means sold below "
        "what they were worth."
    )
    premium_pct: float = Field(description="The same difference as a percentage")
    buyer: MissingStr = Field(default=None, description="Who bought the player")
    applied_immediately: bool = Field(
        description="True for an acceptance: it takes effect at once and cannot be reversed"
    )


class LineupSlot(ComunioModel):
    slot: int = Field(description="Comunio's slot number, 1 to 11")
    position: str = Field(description="What that slot plays")
    player_id: int = Field(description="Player put there")
    player: str = Field(description="That player's name")
    status: str = Field(description="Their availability at the time the lineup was set")


class LineupResult(ComunioModel):
    """What the lineup was set to.

    Comunio answers with nothing but a status, so everything else here is worked out from
    what was sent.
    """

    ok: bool = Field(description="Whether Comunio accepted the lineup")
    tactic: str = Field(description="Formation the lineup was set to")
    fielded: list[LineupSlot] = Field(description="Who ended up in which slot")
    empty_slots: int = Field(description="Slots left unfilled")
    penalty_points: int = Field(
        description="What those empty slots cost, by Comunio's own stated rule of four "
        "points each"
    )
    unavailable: list[str] = Field(
        description="Fielded players who were not ACTIVE — injured, suspended and the like"
    )
    out_of_position: list[str] = Field(
        default_factory=list,
        description="Fielded players put in a slot other than the position they play. "
        "Reported, not refused: Comunio decides whether it accepts them",
    )


class WatchedPlayer(ComunioModel):
    """A player on the watchlist."""

    id: int = Field(description="Player identifier")
    name: str = Field(description="Player name")
    club: str = Field(description="Their club")
    position: str = Field(description="Where they play")

    status: str = Field(description="Availability code")
    status_info: MissingStr = Field(default=None, description="Why they are unavailable")
    disabled: bool = Field(description="Whether the league has this player disabled")

    quoted_price: int = Field(description="Market value, in euros")
    trend: MissingInt = Field(default=None, description="Price movement, negative when falling")
    points: MissingInt = Field(default=None, description="Season points")
    last_points: MissingInt = Field(default=None, description="Points in the last matchday")

    owner: MissingStr = Field(
        default=None, description="Manager who owns them, or null when nobody does"
    )
    owner_id: MissingInt = Field(default=None, description="That manager's identifier")
    unowned: bool = Field(
        description="True when no manager holds them, so they can only arrive via the market"
    )


class Watchlist(ComunioModel):
    total: int = Field(description="How many players are being watched")
    unowned: int = Field(description="How many of them no manager holds")
    players: list[WatchedPlayer]


class WatchResult(ComunioModel):
    ok: bool = Field(description="Whether Comunio accepted the change")
    player_id: int = Field(description="Player added to or removed from the watchlist")
    watching: bool = Field(description="Whether the player is now being watched")


class SquadSummary(ComunioModel):
    """Counts the lineup rules are checked against, so nobody has to recount them."""

    total: int = Field(description="Players in the squad")
    lined_up: int = Field(description="Players in the starting eleven")
    substitutes: int = Field(description="Players named as substitutes")
    unavailable: int = Field(description="Players whose status is not ACTIVE")
    on_market: int = Field(description="Players currently listed for sale")
    by_position: dict[str, int] = Field(description="How many players per position")


class Squad(ComunioModel):
    owner: str | None = Field(default=None, description="Manager the squad belongs to")
    owner_id: int | None = Field(default=None, description="That manager's identifier")
    is_mine: bool = Field(
        default=False, description="Whether this is the signed-in manager's own squad"
    )
    tactic: str = Field(description="Formation the lineup is set up for, e.g. '442'")
    summary: SquadSummary
    players: list[SquadPlayer]
