"""Open transfer offers.

`game:readOffers` returns HTTP 500 unless the request carries the **valueless query flag**
`?current`. It is a bare flag, not `current=true`, so it is appended to the URL rather than
passed as a parameter.

The most valuable thing here is not the offers: it is `credit`. That is what the manager
can actually spend, and thanks to the league's dynamic credit factor it is not the same as
the budget in `get_account`.
"""

from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.market import COMPUTER_USER_ID
from comunio_mcp.comunio.models import Offer, Offers, OffersSummary
from comunio_mcp.comunio.session import Session

OFFERS_LINK = "game:readOffers"

#: A flag with no value. `?current=true` is not what the web app sends.
CURRENT_FLAG = "current"

INCOMING = "incoming"
OUTGOING = "outgoing"


async def fetch_offers(session: Session, client: ComunioClient) -> Offers:
    url = await session.link(OFFERS_LINK)
    payload = await client.get(f"{url}?{CURRENT_FLAG}")
    me = (await session.info()).user_id
    return parse_offers(payload, me)


def parse_offers(payload: Any, me: str) -> Offers:
    offers = [_parse_offer(item, me=me) for item in (payload.get("items") or [])]
    return Offers(
        credit=payload.get("credit", 0),
        has_more=payload.get("hasMore", False),
        summary=_summarise(offers),
        offers=offers,
    )


def _parse_offer(item: dict, *, me: str) -> Offer:
    player = item.get("tradable") or {}
    offerer = item.get("user") or {}
    partner = item.get("tradingPartner") or {}

    offerer_id = offerer.get("id")
    # The manager is on one side or the other. If they made the offer it is outgoing;
    # otherwise somebody wants one of their players.
    direction = OUTGOING if str(offerer_id) == str(me) else INCOMING

    price = item.get("price", 0)
    quoted = player.get("quotedPrice") or 0

    return Offer.model_validate(
        {
            **item,
            "offer_id": item.get("id"),
            "player": player,
            "price": price,
            "premium": price - quoted,
            "premium_pct": round((price - quoted) / quoted * 100, 1) if quoted else 0.0,
            "direction": direction,
            "offered_by": offerer.get("name", "").strip(),
            "offered_by_id": offerer_id,
            "from_computer": offerer_id == COMPUTER_USER_ID,
            "counterparty": partner.get("name", "").strip(),
            "created_at": item.get("datecreated"),
            "changed_at": item.get("datechanged"),
        }
    )


def _summarise(offers: list[Offer]) -> OffersSummary:
    incoming = [offer for offer in offers if offer.direction == INCOMING]
    return OffersSummary(
        total=len(offers),
        incoming=len(incoming),
        outgoing=sum(1 for offer in offers if offer.direction == OUTGOING),
        from_computer=sum(1 for offer in offers if offer.from_computer),
        below_quoted=sum(1 for offer in incoming if offer.premium < 0),
        incoming_total=sum(offer.price for offer in incoming),
    )
