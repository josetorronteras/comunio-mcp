"""The league news feed.

Same endpoint as [`transfers.py`](transfers.py), read for the opposite reason. That module
keeps only `TRANSACTION_TRANSFER` entries and throws the rest away; this one is the rest —
season announcements, community resets, members joining, lineups being changed.

The raw feed is mostly unusable as it stands, and making it usable is the whole job here:

* **Announcement bodies are HTML.** Tags, `<br />`, and entities like `&iexcl;` and
  `&aacute;`. A model reading that spends its context on markup.
* **A `LINEUP_CHANGED` entry carries the whole eleven** — every player with their club,
  their club's logo URL and their photo URL, plus four empty substitute slots. Hundreds of
  fields to say "the formation is now 3-4-3".
* **Every entry carries `_links`** with hrefs for posting comments and pinning the entry.

So each entry is reduced to what it actually says. Nothing is filtered out by type: which
news matters is the reader's call, and `types` is there for them to make it.
"""

import html
import logging
import re
from typing import Any

from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.models import News, NewsEntry, NewsLink, NewsSummary
from comunio_mcp.comunio.session import Session

logger = logging.getLogger(__name__)

NEWS_LINK = "game:news"

#: `originaltypes=true` is load-bearing: without it Comunio collapses the entry types to
#: coarse ones (`TRANSACTION` instead of `TRANSACTION_TRANSFER`) and they cannot be told
#: apart, which is what `types` filters on. `group=true` only nests the entries under
#: dates, which is more work to undo. The web app also sends `type=HIDDEN_NEWS`, which was
#: measured to change nothing.
BASE_PARAMS = "originaltypes=true"

#: **The feed caps a page at 20** however large a limit is requested. That is a property of
#: this endpoint, not of the offer history, which honours what it is given.
PAGE_SIZE = 20

#: Stops a request for a big limit from walking the whole history of the league.
MAX_PAGES = 10

TRANSFER_TYPE = "TRANSACTION_TRANSFER"
LINEUP_TYPE = "LINEUP_CHANGED"

#: `<br>` and the end of a paragraph are the only tags that carry meaning once the markup
#: is gone. Everything else is decoration.
_BREAKS = re.compile(r"<br\s*/?>|</p\s*>|</div\s*>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]{2,}")


def plain_text(raw: Any) -> str | None:
    """Turn Comunio's HTML into something worth putting in a model's context.

    Entities are unescaped *after* tags are stripped, so an `&lt;` in the copy cannot
    become a tag that the stripper then eats.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None

    text = _BREAKS.sub("\n", raw)
    text = _TAGS.sub("", text)
    text = html.unescape(text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text).strip()

    return text or None


async def fetch_news(
    session: Session,
    client: ComunioClient,
    limit: int = PAGE_SIZE,
    types: list[str] | None = None,
) -> News:
    url = await session.link(NEWS_LINK)
    wanted = {kind.upper() for kind in types} if types else None

    entries: list[NewsEntry] = []
    has_more = False

    for page in range(MAX_PAGES):
        payload = await client.get(
            f"{url}?{BASE_PARAMS}&start={page * PAGE_SIZE}&limit={PAGE_SIZE}"
        )
        news = payload.get("newsList") or {}
        raw = news.get("entries") or []
        has_more = bool(news.get("hasMore"))

        entries.extend(parse_news_entries(raw, types=wanted))

        if len(entries) >= limit or not raw or not has_more:
            break
    else:
        logger.info("Stopped after %d pages of news", MAX_PAGES)

    if len(entries) > limit:
        entries, has_more = entries[:limit], True

    return News(summary=_summarise(entries), has_more=has_more, entries=entries)


def parse_news_entries(raw: list[dict], *, types: set[str] | None = None) -> list[NewsEntry]:
    return [
        _parse_entry(entry)
        for entry in raw
        if isinstance(entry, dict) and (types is None or entry.get("type") in types)
    ]


def _parse_entry(entry: dict) -> NewsEntry:
    kind = entry.get("type") or ""
    message = entry.get("message")
    message = message if isinstance(message, dict) else {}

    return NewsEntry(
        id=entry.get("id"),
        date=entry.get("date"),
        edited_at=entry.get("lastEdit"),
        type=kind,
        # Administration entries put the whole announcement in the title and send an empty
        # body, so the title is content here rather than a label.
        title=(entry.get("title") or "").strip(),
        text=plain_text(message.get("text")),
        links=_parse_links(message.get("links")),
        sticky=bool(entry.get("sticky")),
        comments=len(entry.get("comments") or []),
        has_poll=entry.get("poll") is not None,
        tactic=message.get("tactic") if kind == LINEUP_TYPE else None,
        lineup_incomplete=message.get("incomplete") if kind == LINEUP_TYPE else None,
        transfers=_count_transfers(message) if kind == TRANSFER_TYPE else None,
    )


def _parse_links(raw: Any) -> list[NewsLink]:
    """Links inside an announcement body. `anchor` and `target` are presentation."""
    if not isinstance(raw, list):
        return []
    return [
        NewsLink(text=(link.get("text") or "").strip(), url=link.get("url") or "")
        for link in raw
        if isinstance(link, dict) and link.get("url")
    ]


def _count_transfers(message: dict) -> int:
    """How many moves a transfer entry covers.

    Only the count, deliberately. `get_transfers` already parses these properly — prices,
    both sides, who is Comunio — and repeating it here would be a second implementation of
    the same thing, free to drift from the first.
    """
    return sum(len(moves) for moves in message.values() if isinstance(moves, list))


def _summarise(entries: list[NewsEntry]) -> NewsSummary:
    by_type: dict[str, int] = {}
    for entry in entries:
        by_type[entry.type] = by_type.get(entry.type, 0) + 1

    return NewsSummary(total=len(entries), by_type=by_type)
