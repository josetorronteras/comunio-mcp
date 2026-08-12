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


def _listing(
    player_id,
    name,
    position,
    *,
    owner_id,
    owner_name,
    quoted=1_000_000,
    recommended=1_000_000,
    trend=0,
    status="ACTIVE",
    status_info="",
    date="2026-08-10T04:15:06+0200",
):
    return {
        "_links": {"player": {"href": f"https://api.comunio.es/players/{player_id}"}},
        "date": date,
        "remaining": 14,
        "watched": False,
        "_embedded": {
            "player": {
                "_links": {"photo": {"href": "https://api.comunio.es/x/photo"}},
                "id": player_id,
                "name": name,
                "club": {"_links": {}, "id": 5, "name": "Mock FC"},
                "position": position,
                "trend": trend,
                "quotedPrice": quoted,
                "recommendedPrice": recommended,
                "status": status,
                "statusInfo": status_info,
                "points": "-",
                "purchasePrice": 0,
                "watched": False,
            },
            "owner": {
                "_links": {},
                "id": owner_id,
                "name": owner_name,
                "communityId": int(COMMUNITY_ID),
            },
        },
    }


#: Note `quotedPrice` with a capital P — the squad endpoint spells the same concept
#: `quotedprice`. The offset in `date` has no colon (`+0200`), unlike everywhere else.
MARKET_RESPONSE = {
    "_links": {
        "game:exchangemarket:placeoffers": {"href": "https://api.comunio.es/x/offers"},
    },
    "items": [
        _listing(1001, "Delantero Caro", "striker", owner_id=1, owner_name="Computer",
                 quoted=2_650_000, recommended=2_650_000, trend=1),
        _listing(1002, "Defensa Barato", "defender", owner_id=1, owner_name="Computer",
                 quoted=220_000, recommended=220_000, trend=0),
        _listing(1003, "Medio Propio", "midfielder", owner_id=int(USER_ID),
                 owner_name=MANAGER_NAME, quoted=430_000, recommended=440_000, trend=-2),
        _listing(1004, "Medio Lesionado", "midfielder", owner_id=int(USER_ID),
                 owner_name=MANAGER_NAME, quoted=370_000, recommended=360_000,
                 status="WEAKENED", status_info="Lesión muscular"),
        _listing(1005, "Portero Rival", "keeper", owner_id=30000001, owner_name="Rival Uno",
                 quoted=470_000, recommended=450_000, trend=4),
    ],
    "nextTransfersDateTime": "2026-08-11T03:00:00+02:00",
    "dailyTransfersProcessed": True,
}


def _offer(
    offer_id,
    player_id,
    name,
    position,
    *,
    quoted,
    price,
    offerer_id,
    offerer_name,
    partner_id,
    partner_name,
    status="ACTIVE",
):
    return {
        "id": offer_id,
        "type": "SALE",
        "tradable": {
            "id": player_id,
            "name": name,
            "club": {"id": 5, "name": "Mock FC", "_links": {}},
            "position": position,
            "trend": 0,
            "quotedPrice": quoted,
            "recommendedPrice": quoted,
            "status": status,
            "statusInfo": "",
            "points": 0,
            "purchasePrice": 0,
            # A boolean sent as a string, unlike `watched` elsewhere.
            "onWatchlist": "false",
            "owner": {"id": partner_id, "name": partner_name, "_links": {}},
            "displayName": None,
            "_links": {"photo": {"href": "https://api.comunio.es/x/photo"}},
        },
        "user": {"id": offerer_id, "name": offerer_name, "_links": {}},
        # Comunio pads some manager names with a trailing space.
        "tradingPartner": {"id": partner_id, "name": f"{partner_name} ", "_links": {}},
        "price": price,
        "datecreated": "2026-08-10T04:24:03+02:00",
        "datechanged": "2026-08-10T04:24:03+02:00",
        "state": "PENDING",
        "exchange": False,
        "tradablesOffered": [],
        "tradablesDemanded": [],
        "_links": {"game:offer:decline": {"href": "https://api.comunio.es/x/offers/1"}},
    }


#: `credit` is deliberately different from the budget in the index fixture: the league's
#: dynamic credit factor means they are not the same number.
OFFERS_RESPONSE = {
    "credit": 29_475_000,
    "items": [
        # Above market value.
        _offer(9000001, 1876, "Medio Uno", "midfielder", quoted=430_000, price=439_000,
               offerer_id=1, offerer_name="Computer",
               partner_id=int(USER_ID), partner_name=MANAGER_NAME),
        # Below market value — worth flagging, an agent should not accept blindly.
        _offer(9000002, 4038, "Medio Dos", "midfielder", quoted=3_630_000, price=3_528_400,
               offerer_id=1, offerer_name="Computer",
               partner_id=int(USER_ID), partner_name=MANAGER_NAME),
        # An offer the manager made for somebody else's player.
        _offer(9000003, 5001, "Delantero Rival", "striker", quoted=1_000_000, price=1_200_000,
               offerer_id=int(USER_ID), offerer_name=MANAGER_NAME,
               partner_id=30000001, partner_name="Rival Uno"),
    ],
    "hasMore": False,
    "_links": {"game:placeOffers": {"href": "https://api.comunio.es/x/offers"}},
}


RIVAL_ID = 30000001
RIVAL_NAME = "Rival Uno"


def _rival_player(player_id, name, position, *, status="ACTIVE", status_info=""):
    player = _player(player_id, name, position, status=status, status_info=status_info)
    # Comunio gives no price recommendation for players you do not own, and a rival's
    # lineup is never populated here.
    player["recommendedprice"] = -1
    player["owner"] = {"id": RIVAL_ID, "name": RIVAL_NAME}
    return player


#: A rival's squad: same endpoint, different user id.
RIVAL_SQUAD_RESPONSE = {
    "items": [
        _rival_player(2001, "Rival Portero", "keeper"),
        _rival_player(2002, "Rival Defensa", "defender"),
        # A status the manager's own squad has not shown: INJURED, distinct from WEAKENED.
        _rival_player(2003, "Rival Roto", "striker", status="INJURED",
                      status_info="Fractura de peroné"),
        # A fourth status: suspended after a red card.
        _rival_player(2004, "Rival Sancionado", "midfielder", status="RED_BANNED"),
    ],
    "tactic": "442",
    "_links": {"self": {"href": f"https://api.comunio.es/users/{RIVAL_ID}/squad"}},
}


def _settled(
    offer_id,
    player_id,
    name,
    position,
    *,
    owner_id,
    owner_name,
    user_id,
    user_name,
    price,
    quoted,
    offer_type="SALE",
    status="ACTIVE",
    created="2026-08-10T04:24:03+02:00",
    changed="2026-08-11T04:31:06+02:00",
):
    """One settled offer, shaped like `game:readOffersHistory` returns them.

    `owner` is who held the player, `user` is whose offer it was — the seller and the
    buyer. `type` is deliberately set to values that contradict the direction, because in
    real data it does: SALE appears on players moving both ways.
    """
    return {
        "id": offer_id,
        "type": offer_type,
        "tradable": {
            "id": player_id,
            "name": name,
            "club": {
                "id": 5,
                "name": "Mock FC",
                "_links": {
                    "self": {"href": "https://api.comunio.es/clubs/5"},
                    "logo": {"href": "https://api.comunio.es/clubs/5/logo"},
                },
            },
            "position": position,
            "trend": 0,
            "quotedPrice": quoted,
            # Always 0 here, unlike the market endpoint where it is a real recommendation.
            "recommendedPrice": 0,
            "status": status,
            "statusInfo": None,
            "points": 0,
            "purchasePrice": 0,
            "onWatchlist": None,
            # Padded with a trailing space, as Comunio sends it.
            "owner": {"id": owner_id, "name": f"{owner_name} ", "_links": {}},
            "displayName": None,
            "_links": {
                "photo": {"href": f"https://api.comunio.es/players/{player_id}/photo"},
                "detailedInfo": {"href": "https://api.comunio.es/x/detail"},
            },
        },
        "user": {"id": user_id, "name": user_name, "_links": {}},
        # Repeats the owner and so adds nothing.
        "tradingPartner": {"id": owner_id, "name": f"{owner_name} ", "_links": {}},
        "price": price,
        "datecreated": created,
        "datechanged": changed,
        "state": "PROCESSED",
        "exchange": False,
        "tradablesOffered": [],
        "tradablesDemanded": [],
        "_links": {"game:offer:withdraw": {"href": "https://api.comunio.es/x/offers/1"}},
    }


#: Settled offers. `credit` comes back null here, unlike the open-offers endpoint.
#: The `type` values are the important part of this fixture: SALE appears on a player
#: going to Comunio *and* on one coming from it, so it cannot say which way a deal went.
OFFERS_HISTORY_RESPONSE = {
    "credit": None,
    "items": [
        # Bought from Comunio, and filed as PURCHASE.
        _settled(8000001, 7001, "Fichaje Uno", "midfielder",
                 owner_id=1, owner_name="Computer", user_id=int(USER_ID), user_name=MANAGER_NAME,
                 price=2_300_000, quoted=1_780_000, offer_type="PURCHASE"),
        # Also bought from Comunio — but filed as SALE. Same direction, different type.
        _settled(8000002, 7002, "Fichaje Dos", "defender",
                 owner_id=1, owner_name="Computer", user_id=30000001, user_name="Rival Uno",
                 price=16_000_000, quoted=15_900_000, offer_type="SALE"),
        # Sold back to Comunio, filed as SALE as well.
        _settled(8000003, 7003, "Venta Uno", "keeper",
                 owner_id=30000002, owner_name="Rival Dos", user_id=1, user_name="Computer",
                 price=659_100, quoted=1_080_000, offer_type="SALE",
                 changed="2026-08-10T06:52:15+02:00"),
        # The manager's own sale, and a name padded on both sides.
        _settled(8000004, 7004, " Venta Propia ", "striker",
                 owner_id=int(USER_ID), owner_name=MANAGER_NAME, user_id=1, user_name="Computer",
                 price=366_700, quoted=280_000, status="WEAKENED",
                 changed="2026-08-10T14:21:47+02:00"),
        # Between two managers, with Comunio on neither side.
        _settled(8000005, 7005, "Traspaso Directo", "midfielder",
                 owner_id=30000001, owner_name="Rival Uno",
                 user_id=30000003, user_name="Rival Tres",
                 price=4_817_400, quoted=4_970_000,
                 changed="2026-08-09T12:22:32+02:00"),
    ],
    "hasMore": False,
    "_links": {"game:placeOffers": {"href": "https://api.comunio.es/x/offers"}},
}


def _move(player_id, name, from_id, from_name, to_id, to_name, price, immediate=None):
    move = {
        "tradable": {"id": player_id, "name": name},
        "from": {"id": from_id, "name": from_name},
        "to": {"id": to_id, "name": to_name},
        "price": price,
    }
    if immediate:
        move["immediateTransferTime"] = immediate
    return move


def _entry(entry_id, date, kind, title, message, **extra):
    """Wraps a news entry in the envelope every one of them carries.

    `_links` is here because it is in every real entry, carrying hrefs for posting a
    comment and pinning the item — the kind of thing the models have to drop.
    """
    return {
        "id": entry_id,
        "date": date,
        "lastEdit": extra.pop("last_edit", None),
        "type": kind,
        "title": title,
        "message": message,
        "owner": {"id": 1, "name": "Computer"},
        "recipient": {"id": None, "name": ""},
        "comments": extra.pop("comments", []),
        "sticky": extra.pop("sticky", False),
        "poll": extra.pop("poll", None),
        "partner": extra.pop("partner", None),
        "_links": {
            "self": {"href": f"/communities/{COMMUNITY_ID}/news/{entry_id}"},
            "createComment": {"href": "https://api.comunio.es/x/comments"},
            "setSticky": {"href": "https://api.comunio.es/x/sticky"},
        },
    }


#: A lineup entry's real weight: every player repeated with their club, the club's logo
#: URL and a photo URL. Eleven of these say nothing the `tactic` field does not.
def _lineup_player(player_id, name):
    return {
        "id": player_id,
        "name": name,
        "points": 0,
        "liveSubstituted": False,
        "club": {
            "id": 5,
            "name": "Mock FC",
            "_links": {
                "self": {"href": "https://api.comunio.es/clubs/5"},
                "logo": {"href": "https://api.comunio.es/clubs/5/logo"},
            },
        },
        "_links": {
            "photo": {"href": f"https://api.comunio.es/players/{player_id}/photo"},
            "detailedInfo": {"href": f"https://api.comunio.es/x/players/{player_id}"},
        },
    }


#: The marketing body, with the markup that makes it unreadable: entities for every
#: accent, `<br />` for line breaks and a link buried in an anchor.
MARKETING_HTML = (
    "<p>&iexcl;Hola managers! <br /><br /> Empieza la <strong>temporada"
    "</strong> y hay <em>sorteo</em>. <br /><br /> Puedes leer las bases "
    '<a href="https://example.invalid/bases">AQU&Iacute;</a>. <br /><br /> '
    "Saludos, <br /> Equipo de Comunio</p>"
)


#: News entries as the flat `entries` list, which is what `originaltypes=true` without
#: `group=true` returns. Only one of these is a transfer; the rest is what the feed is
#: mostly made of, including a marketing entry far longer than any transfer.
NEWS_ENTRIES = [
    _entry(
        1, "2026-08-10T04:30:27+02:00", "TRANSACTION_TRANSFER", "Fichajes",
        {
            "FROM_COMPUTER": [
                _move(7001, "Fichaje Uno", 1, "Computer", 30000001, "Rival Uno", 7_100_000),
                _move(7002, "Fichaje Dos", 1, "Computer", int(USER_ID), MANAGER_NAME, 1_650_020),
            ],
            "TO_COMPUTER": [
                _move(7003, "Venta Uno", 30000002, "Rival Dos ", 1, "Computer",
                      659_100, immediate="06:52"),
            ],
        },
        last_edit="2026-08-10T14:21:47+02:00",
    ),
    _entry(
        2, "2026-08-09T04:31:23+02:00", "SYSTEM_ADMINISTRATION", "¡Empieza la temporada!",
        {
            "text": MARKETING_HTML,
            "links": [
                {"text": "AQUÍ", "url": "https://example.invalid/bases",
                 "anchor": "", "target": ""}
            ],
        },
        sticky=True,
        comments=[{"id": 11}, {"id": 12}],
        partner={"name": "Comunio", "url": "http://www.comunio.es"},
    ),
    _entry(
        3, "2026-08-08T13:59:00+02:00", "LINEUP_CHANGED",
        "La alineación se ha cambiado, la nueva alineación es: 4-4-2",
        {
            "lineup": {
                "keeper": [_lineup_player(1001, "Portero Uno")],
                "defender": [_lineup_player(1003, "Defensa Uno")],
                "midfielder": [],
                "striker": [_lineup_player(1008, "Delantero Uno")],
            },
            "substitutes": {"striker": _lineup_player(0, None)},
            "incomplete": True,
            "tactic": "442",
            "promotion": False,
        },
    ),
    _entry(
        4, "2026-08-07T10:07:44+02:00", "MEMBER_ADMINISTRATION", "¡Nuevo miembro!",
        {"text": "Alguien se ha unido a la comunidad.", "links": []},
    ),
    # The whole announcement is in the title and the body is empty — so a tool that only
    # reads `text` would report this one as saying nothing.
    _entry(
        5, "2026-08-07T21:36:21+02:00", "COMMUNITY_ADMINISTRATION",
        "El administrador ha reiniciado la comunidad.",
        {"text": "", "links": []},
    ),
]

NEWS_RESPONSE = {"newsList": {"entries": NEWS_ENTRIES, "hasMore": True, "_links": {}}}


#: A player detail sheet. `totalPoints` is the dash again, `preferredFoot` and
#: `countryCode` come back empty, and the recent-average window is blank before any
#: matches are graded.
PLAYER_RESPONSE = {
    "playerId": 1400,
    "name": "Jugador Detalle",
    "price": 4_750_000,
    "totalPoints": "-",
    "lastPoints": 4,
    "status": "YELLOW_RED_BANNED",
    "statusInfo": "",
    "blogTag": "2026-08-01",
    "type": "PLAYER",
    "club": {"id": 5, "name": "Mock FC", "abbreviation": ""},
    "general": {
        "playedGames": 34,
        "ratedGames": 33,
        "totalGoals": 12,
        "totalPenalties": 3,
        "manOfTheMatchAmount": 5,
    },
    "average": {
        "grade": "2.8",
        "points": "6.4",
        "lastXMatchdays": {"matchesAmount": 0, "grade": "", "points": ""},
    },
    "extendedInfo": {
        "dob": "1995-03-14",
        "nationality": "ESP",
        "countryCode": "",
        "height": 189,
        "weight": 91,
        "preferredFoot": None,
        "jerseyNumber": 13,
    },
    "cards": {"yellow": 4, "yellowRed": 1, "red": 0},
    "historical": {
        "points": [
            {"season": "25/26", "points": "212", "eventId": 1},
            {"season": "24/25", "points": "198", "eventId": 2},
        ]
    },
    "communityId": int(COMMUNITY_ID),
    "userId": int(USER_ID),
    "owner": {"id": int(USER_ID), "name": f"{MANAGER_NAME} "},
    "buyoutClauseInfo": {
        "dateOfAvailability": None,
        "paid": False,
        "blockDays": 3,
        "paidBy": 0,
        "price": 9_500_000,
    },
    "nextMatches": [
        {
            "matchdayNr": 1,
            "homeClub": {"id": 5, "name": "Mock FC", "abbreviation": "mck"},
            "guestClub": {"id": 99, "name": "Rival FC", "abbreviation": "rvl"},
            "kickoff": "2026-08-15T19:30:00+02:00",
        },
        {
            "matchdayNr": 2,
            "homeClub": {"id": 99, "name": "Rival FC", "abbreviation": "rvl"},
            "guestClub": {"id": 5, "name": "Mock FC", "abbreviation": "mck"},
            "kickoff": "2026-08-22T21:00:00+02:00",
        },
    ],
    "watched": True,
    # Marketing links the model has no use for.
    "externalLinks": {
        "forum": {"name": "Foro", "text": "Habla del jugador", "url": "https://example.invalid/f"},
        "blog": {"name": "Magazine", "text": "Noticias", "url": "https://example.invalid/b"},
    },
    "season": "26/27",
    "inLineup": "",
    "purchaseInfo": {"date": "2026-08-07", "price": 4_200_000},
}


@pytest.fixture
def index_response() -> dict:
    return INDEX_RESPONSE


@pytest.fixture
def player_response() -> dict:
    return PLAYER_RESPONSE


@pytest.fixture
def news_entries() -> list[dict]:
    return NEWS_ENTRIES


@pytest.fixture
def offers_history_response() -> dict:
    return OFFERS_HISTORY_RESPONSE


@pytest.fixture
def rival_squad_response() -> dict:
    return RIVAL_SQUAD_RESPONSE


@pytest.fixture
def offers_response() -> dict:
    return OFFERS_RESPONSE


@pytest.fixture
def market_response() -> dict:
    return MARKET_RESPONSE


@pytest.fixture
def squad_response() -> dict:
    return SQUAD_RESPONSE


@pytest.fixture
def standings_response() -> dict:
    return STANDINGS_RESPONSE
