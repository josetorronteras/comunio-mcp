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


@pytest.fixture
def index_response() -> dict:
    return INDEX_RESPONSE
