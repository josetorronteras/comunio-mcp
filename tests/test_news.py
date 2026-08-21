import asyncio
import json

import httpx2
import pytest

from comunio_mcp.comunio.auth import ComunioAuth
from comunio_mcp.comunio.client import ComunioClient
from comunio_mcp.comunio.news import fetch_news, parse_news_entries, plain_text
from comunio_mcp.comunio.session import Session
from comunio_mcp.config import Settings
from tests.conftest import COMMUNITY_ID, MARKETING_HTML, USER_ID

SETTINGS = Settings(username="manager", password="s3cret", timezone="Europe/Madrid")


@pytest.fixture
def entries(news_entries):
    return parse_news_entries(news_entries)


def _by_id(entries, entry_id):
    return next(entry for entry in entries if entry.id == entry_id)


def test_every_entry_survives_whatever_its_type(entries, news_entries):
    # Which news matters is the reader's call, so nothing is dropped by type. This is the
    # opposite of get_transfers, which keeps only the transfer entries.
    assert len(entries) == len(news_entries)
    assert {entry.type for entry in entries} == {
        "TRANSACTION_TRANSFER",
        "SYSTEM_ADMINISTRATION",
        "LINEUP_CHANGED",
        "MEMBER_ADMINISTRATION",
        "COMMUNITY_ADMINISTRATION",
    }


def test_the_body_comes_back_as_plain_text(entries):
    announcement = _by_id(entries, 2)

    assert announcement.text is not None
    assert "<" not in announcement.text
    assert "&iexcl;" not in announcement.text
    # The entities became the characters they stand for.
    assert announcement.text.startswith("¡Hola managers!")
    assert "AQUÍ" in announcement.text


def test_no_markup_or_urls_leak_through_anywhere(entries):
    serialised = json.dumps([e.model_dump(mode="json") for e in entries], ensure_ascii=False)

    # Photos, club logos, comment hrefs and the pinning endpoint are all in the raw feed.
    assert "api.comunio.es" not in serialised
    assert "/photo" not in serialised
    assert "<p>" not in serialised
    assert "&iexcl;" not in serialised


def test_links_are_kept_but_stripped_of_presentation(entries):
    announcement = _by_id(entries, 2)

    assert len(announcement.links) == 1
    assert announcement.links[0].text == "AQUÍ"
    assert announcement.links[0].url == "https://example.invalid/bases"


def test_a_lineup_entry_collapses_to_its_formation(entries):
    lineup = _by_id(entries, 3)

    # The raw entry carries the whole eleven with photos and club logos to say this much.
    assert lineup.tactic == "442"
    assert lineup.lineup_incomplete is True
    assert lineup.text is None


def test_a_transfer_entry_is_counted_not_reparsed(entries):
    transfer = _by_id(entries, 1)

    # get_transfers owns the detail. Repeating it here would be free to drift from it.
    assert transfer.transfers == 3
    assert transfer.edited_at is not None


def test_the_type_specific_fields_are_null_elsewhere(entries):
    member = _by_id(entries, 4)

    assert member.tactic is None
    assert member.lineup_incomplete is None
    assert member.transfers is None


def test_an_administration_entry_carries_its_news_in_the_title(entries):
    reset = _by_id(entries, 5)

    # Comunio sends an empty body here, so a reader that only looked at `text` would
    # report the league being reset as an entry that says nothing.
    assert reset.text is None
    assert "reiniciado la comunidad" in reset.title


def test_the_envelope_is_reported(entries):
    announcement = _by_id(entries, 2)

    assert announcement.sticky is True
    assert announcement.comments == 2
    assert announcement.has_poll is False


def test_types_filters_case_insensitively(news_entries):
    filtered = parse_news_entries(news_entries, types={"LINEUP_CHANGED"})

    assert [entry.id for entry in filtered] == [3]


def test_plain_text_returns_none_for_an_empty_body():
    assert plain_text("") is None
    assert plain_text("   ") is None
    assert plain_text(None) is None
    assert plain_text({"not": "a string"}) is None


def test_plain_text_keeps_line_breaks_without_piling_them_up():
    text = plain_text(MARKETING_HTML)

    assert "\n\n\n" not in text
    assert "\n" in text


def test_an_escaped_angle_bracket_is_not_eaten_as_a_tag():
    # Unescaping before stripping would turn this into a tag and then delete it.
    assert plain_text("<p>3 &lt; 5 y 5 &gt; 3</p>") == "3 < 5 y 5 > 3"


class FakeApi:
    """Answers login, the index and the news endpoint, one page at a time."""

    def __init__(self, pages) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/login":
            return httpx2.Response(
                200,
                json={
                    "access_token": "a",
                    "expires_in": 1800,
                    "token_type": "Bearer",
                    "scope": "",
                    "refresh_token": "r",
                },
            )
        if request.url.path == "/":
            return httpx2.Response(
                200,
                json={
                    "user": {"id": USER_ID},
                    "community": {"id": COMMUNITY_ID},
                    "_links": {
                        "game:news": {
                            "href": "https://api.comunio.es/communities/"
                            f"{COMMUNITY_ID}/users/{USER_ID}/news"
                        }
                    },
                },
            )

        self.requested.append(str(request.url))
        page = self.pages.pop(0) if self.pages else {"entries": [], "hasMore": False}
        return httpx2.Response(200, json={"newsList": page})


def _run(handler, body):
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def run():
        async with http:
            client = ComunioClient(http, ComunioAuth(http, SETTINGS))
            return await body(Session(client), client)

    return asyncio.run(run())


def test_originaltypes_is_sent_or_the_types_collapse(news_entries):
    # Without it Comunio sends TRANSACTION instead of TRANSACTION_TRANSFER and the kinds
    # cannot be told apart, which is the whole basis of `types` and of get_transfers.
    handler = FakeApi([{"entries": news_entries, "hasMore": False}])

    _run(handler, lambda s, c: fetch_news(s, c))

    assert "originaltypes=true" in handler.requested[0]


def test_it_stops_at_the_limit_and_says_there_is_more(news_entries):
    handler = FakeApi([{"entries": news_entries, "hasMore": True}])

    result = _run(handler, lambda s, c: fetch_news(s, c, limit=2))

    assert len(result.entries) == 2
    assert result.has_more is True
    assert result.summary.total == 2


def test_it_pages_until_it_has_enough(news_entries):
    handler = FakeApi(
        [
            {"entries": news_entries, "hasMore": True},
            {"entries": news_entries, "hasMore": False},
        ]
    )

    result = _run(handler, lambda s, c: fetch_news(s, c, limit=10))

    assert len(handler.requested) == 2
    assert "start=20" in handler.requested[1]
    assert len(result.entries) == 10


def test_it_stops_when_comunio_says_there_is_no_more(news_entries):
    handler = FakeApi([{"entries": news_entries, "hasMore": False}])

    result = _run(handler, lambda s, c: fetch_news(s, c, limit=100))

    assert len(handler.requested) == 1
    assert result.has_more is False


def test_the_summary_counts_each_type(news_entries):
    handler = FakeApi([{"entries": news_entries, "hasMore": False}])

    result = _run(handler, lambda s, c: fetch_news(s, c))

    assert result.summary.by_type["TRANSACTION_TRANSFER"] == 1
    assert result.summary.by_type["MEMBER_ADMINISTRATION"] == 1
    assert sum(result.summary.by_type.values()) == result.summary.total


def test_types_is_matched_case_insensitively_through_the_fetch(news_entries):
    handler = FakeApi([{"entries": news_entries, "hasMore": False}])

    result = _run(handler, lambda s, c: fetch_news(s, c, types=["lineup_changed"]))

    assert [entry.type for entry in result.entries] == ["LINEUP_CHANGED"]


@pytest.mark.parametrize("limit", [0, -5])
def test_a_limit_below_one_is_refused_before_anything_is_sent(limit):
    # Fetching a page only to throw all of it away is a request made for nothing.
    handler = FakeApi([])

    with pytest.raises(ValueError):
        _run(handler, lambda s, c: fetch_news(s, c, limit=limit))

    assert handler.requested == []
