"""A stand-in for a `GET /` response.

**Every value here is invented.** Only the *shape* is copied from a real response:
numbers arrive as strings, rules sit under `community.rules.items`, "no limit" is an
empty string, and `_links` mixes hrefs that carry ids with hrefs that keep `:placeholder`
segments.

The personal-looking fields (email, invitation code, Google identifiers) are fabricated on
purpose, so the tests can prove the models drop them.
"""

import pytest

USER_ID = "10000001"
COMMUNITY_ID = "20000002"
MANAGER_NAME = "MOCK MANAGER"
LEAGUE_NAME = "3ª DIVISIÓN DE PRUEBA"

INDEX_RESPONSE = {
    "user": {
        "id": USER_ID,
        "name": MANAGER_NAME,
        "firstName": "Mock",
        "lastName": "",
        "isLeader": False,
        "type": "PLUS_TMP",
        "budget": "15000000",
        "teamValue": "42500000",
        "teamCount": "18",
        "teamCountLinedup": "11",
        "salaries": "0",
        "points": "37",
        "tactic": "433",
        "expires": 26,
        "teamType": "BASIC",
        "registered": "2020-01-01T00:00:00+01:00",
        "moderator": False,
        "isAdmin": False,
        "invitationCode": "FAKE-INVITE==",
        "ppidGoogle": "FAKE-PPID==",
        "lastAction": "2020-01-02T00:00:00+01:00",
        "email": "mock@example.invalid",
        "isGuest": False,
        "_links": {"self": {"href": f"https://api.comunio.es/users/{USER_ID}"}},
    },
    "community": {
        "id": COMMUNITY_ID,
        "name": LEAGUE_NAME,
        "password": "",
        "type": "BASIC",
        "rules": {
            "items": {
                "type": "BASIC",
                "private": True,
                "language": "es_ES",
                "members": 8,
                "salaries": False,
                "public_transaction_values": True,
                "max_days_offers_are_pending": "0",
                "max_days_offers_are_pending_users": "0",
                "tradables_on_exchangemarket": "10",
                "players_tradables_on_exchangemarket": "",
                "max_tradables_per_user": "",
                "injured_tradable_offer_factor": "1",
                "sales_ban": "0",
                "sales_ban_pro_offers": "0",
                "second_highest_offers": False,
                "players_member_per_club": "0",
                "tradablechange": False,
                "creditfactor": "dynamic",
                "new_members": "ASSIGN_ANEW",
                "locked": False,
                "description": "",
                "next_season": "KEEP_ALL",
                "anonymous_bidding": False,
                "buyout_clause": False,
                "buyout_clause_factor": "0",
                "buyout_clause_trade_lock": "0",
            },
            "_links": {
                "self": {"href": f"https://api.comunio.es/communities/{COMMUNITY_ID}/rules"}
            },
        },
        "invitationCode": "FAKE-INVITE==",
        "_links": {"self": {"href": f"https://api.comunio.es/communities/{COMMUNITY_ID}"}},
    },
    "_links": {
        "self": {"href": "https://api.comunio.es/"},
        # Ids already baked in.
        "game:lineup": {
            "href": f"https://api.comunio.es/communities/{COMMUNITY_ID}/users/{USER_ID}/lineup"
        },
        "game:tradables": {
            "href": f"https://api.comunio.es/communities/{COMMUNITY_ID}/players"
        },
        # Templated, even though its siblings are not.
        "game:squad": {"href": "https://api.comunio.es/users/:userId/squad"},
        "game:tradable": {
            "href": (
                "https://api.comunio.es/communities/:communityId/users/:userId"
                "/players/:playerId"
            )
        },
        "game:currentMatchday": {"href": "https://api.comunio.es/matchdays/current"},
    },
}


def _player(
    player_id,
    name,
    position,
    *,
    club=("Mock FC", 1),
    points="-",
    last_points=None,
    average_points=0,
    status="ACTIVE",
    status_info="",
    quoted=1_000_000,
    recommended=-1,
    linedup=False,
    slot="",
    substitute=False,
    on_market=False,
    next_match=True,
):
    club_name, club_id = club
    return {
        "id": player_id,
        "name": name,
        "club": {
            "id": club_id,
            "name": club_name,
            "_links": {"self": {"href": f"https://api.comunio.es/clubs/{club_id}"}},
        },
        "points": points,
        "lastPoints": last_points,
        "averagePoints": average_points,
        "matchdayPoints": 0,
        "status": status,
        "statusInfo": status_info,
        "position": position,
        "pos": slot,
        "quotedprice": quoted,
        "recommendedprice": recommended,
        "linedup": linedup,
        "purchaseInfo": None,
        "nextMatch": {
            "id": "999001",
            "home": {"id": club_id, "name": club_name, "_links": {}},
            "guest": {"id": 99, "name": "Rival FC", "_links": {}},
            "kickoff": "2026-08-15T19:30:00+02:00",
        }
        if next_match
        else None,
        "withinSquad": True,
        "owner": {"id": int(USER_ID), "name": MANAGER_NAME},
        "nextSeason": False,
        "hasAcceptedOffers": False,
        "hasAcceptedBuyoutClauseOffer": False,
        "motm": False,
        "watched": False,
        "matchStatus": "finished",
        "isExchangeable": False,
        "notLiveExchangeableReason": "",
        "substitute": substitute,
        "wasLiveSubstituted": False,
        "onMarket": on_market,
        "_links": {
            "self": {"href": f"https://api.comunio.es/players/{player_id}"},
            "photo": {"href": f"https://api.comunio.es/players/{player_id}/photo"},
        },
    }


#: Every quirk of the real payload is represented here on purpose:
#: `points` as a dash, `lastPoints` both as a numeric string and as null,
#: `averagePoints` as a string in one row and an int in another, `recommendedprice` as
#: the -1 sentinel, `pos` empty until a player is lined up, an injured player, and a
#: player with no fixture scheduled.
SQUAD_RESPONSE = {
    "items": [
        _player(1001, "Portero Uno", "keeper", linedup=True, slot="1", average_points="0"),
        _player(1002, "Portero Dos", "keeper", quoted=470_000, recommended=450_000,
                on_market=True, last_points="4"),
        _player(1003, "Defensa Uno", "defender", linedup=True, slot="2"),
        _player(1004, "Defensa Dos", "defender", linedup=True, slot="3"),
        _player(1005, "Defensa Tres", "defender", substitute=True),
        _player(1006, "Medio Uno", "midfielder", status="WEAKENED",
                status_info="Lesión muscular", next_match=False),
        _player(1007, "Medio Dos", "midfielder", on_market=True, recommended=360_000),
        _player(1008, "Delantero Uno", "striker", linedup=True, slot="11",
                quoted=11_390_000, average_points=3.5),
    ],
    "tactic": "442",
    "_links": {
        "self": {"href": f"https://api.comunio.es/users/{USER_ID}/squad"},
        "game:exchangemarket:addplayer": {"href": "https://api.comunio.es/x/addplayer"},
    },
}


def _standing(manager_id, name, *, total=0, last="-", live=None, team_value=0, negative=False):
    return {
        "totalPoints": total,
        "lastPoints": last,
        "totalPerennialPoints": 0,
        "livePoints": live,
        "playersPossiblyScoredAmount": 0,
        "_links": {"user": {"href": f"https://api.comunio.es/users/{manager_id}"}},
        "_embedded": {
            "user": {
                "id": manager_id,
                "name": name,
                "blocked": False,
                "type": None,
                "leagueId": None,
                "leagueName": None,
                "negativeBudget": negative,
                "position": 0,
                "firstName": "Real Name",
                "login": "secret-login",
                "_links": {"self": {"href": f"https://api.comunio.es/users/{manager_id}"}},
            },
            "teamInfo": {
                "teamValue": team_value,
                "tactic": "",
                "seasons": None,
                "badges": {"entries": [], "_links": {}},
                "_links": {"game:squad": {"href": "https://api.comunio.es/x/squad"}},
            },
        },
    }


#: Rival managers are invented. `position` is 0 for everyone, as it is before the season
#: starts, so rank has to come from the order of the list. `lastPoints` is a dash.
STANDINGS_RESPONSE = {
    "id": "total",
    "items": [
        _standing(30000001, "Rival Uno", total=42, last="7", team_value=54_750_000),
        _standing(30000002, "Rival Dos", total=35, team_value=48_420_000, negative=True),
        _standing(int(USER_ID), MANAGER_NAME, total=30, last="3", team_value=42_500_000),
        _standing(30000003, "Rival Tres", team_value=26_000_000),
    ],
    "restartItems": None,
    "historicalItems": None,
    "key": None,
    "secondHalfStarted": False,
    "_links": {"self": {"href": "https://api.comunio.es/x/standings"}},
    "_embedded": {"formerEventsWithPoints": {"events": []}},
}


@pytest.fixture
def index_response() -> dict:
    return INDEX_RESPONSE


@pytest.fixture
def squad_response() -> dict:
    return SQUAD_RESPONSE


@pytest.fixture
def standings_response() -> dict:
    return STANDINGS_RESPONSE
