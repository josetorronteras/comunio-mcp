# The Comunio API

`api.comunio.es` is the private backend behind `www.comunio.es`. There is no published
specification and no official client: what follows was captured from the web app's own
traffic and is documented here so the behaviour is written down rather than rediscovered.

Nothing here is a stable contract. It can change without notice.

## Authentication

One endpoint does both login and refresh, told apart by the request body.

```
POST https://api.comunio.es/login
content-type: application/json
```

**Login**

```json
{ "username": "…", "password": "…", "tzoffset": 2 }
```

**Refresh** — sent with the current (possibly expired) access token in an
`authorization: Bearer …` header:

```json
{ "refresh_token": "…" }
```

**Both return the same shape**

```json
{
  "access_token": "…",
  "expires_in": 1800,
  "token_type": "Bearer",
  "scope": "",
  "refresh_token": "…"
}
```

### Three things that matter

- **Access tokens last 30 minutes.** Refreshing is not optional for a long-lived server.
- **Refresh tokens rotate.** Every refresh returns a *new* `refresh_token`; keep the
  latest or the next refresh fails. `ComunioAuth` always replaces the whole token.
- **`tzoffset` is the UTC offset in hours**, and Madrid is `+2` in summer and `+1` in
  winter. It is computed from `COMUNIO_TIMEZONE` via `zoneinfo`, never hardcoded — a
  constant would quietly start lying at the next DST change. The same reasoning applies
  to the `x-timezone` header, which the web app sends on every request and which
  presumably drives the timestamps the API returns. That matters for anything
  deadline-related.

### Headers

**Every request reproduces the captured browser request verbatim.** The one request we
know Comunio accepts is the one the web app makes; sending a tidier subset would be an
untested change against a private backend that may well have something in front of it
inspecting `user-agent` or `sec-fetch-*`. Fidelity is the point, so the full set lives in
`BROWSER_HEADERS` and is pinned by a test.

```
accept: application/json, text/plain, */*
accept-language: es-ES,es;q=0.7
content-type: application/json
origin: https://www.comunio.es
priority: u=1, i
referer: https://www.comunio.es/
sec-ch-ua: "Not;A=Brand";v="8", "Chromium";v="150", "Brave";v="150"
sec-ch-ua-mobile: ?1
sec-ch-ua-platform: "Android"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
sec-gpc: 1
user-agent: Mozilla/5.0 (Linux; Android 15; Pixel 9) … Mobile Safari/537.36
x-timezone: Europe/Madrid
```

Only two are dynamic: `x-timezone` comes from `COMUNIO_TIMEZONE`, and `user-agent` can be
replaced with `COMUNIO_USER_AGENT` without touching code.

Do not trim this list to what "looks necessary" without testing against the real API
first — and if you do trim it, record which headers turned out to be load-bearing.

## The index: `GET /`

The root is a HAL-style index and the entry point to everything else. It returns the
signed-in manager, their league, and `_links` — **88 named routes** covering the whole
API. No path is hardcoded anywhere else in this project; they all come from here.

```
game:squad                  game:lineup              game:exchangemarket (the market)
game:readOffers             game:watchlist           game:currentMatchday
game:tradableQuoteHistory   game:standings           game:statement      …
```

### Links come in two shapes

Sometimes for sibling routes, which is why the resolver has to handle both:

```
game:lineup   →  /communities/<communityId>/users/<userId>/lineup    ids already baked in
game:squad    →  /users/:userId/squad                                templated
game:tradable →  /communities/:communityId/users/:userId/players/:playerId
```

`Session.link()` substitutes `:placeholder` segments, defaulting `userId` and
`communityId` to the signed-in manager and their league, and **refuses to return a URL
that still has placeholders** — a half-resolved path would 404 in a confusing way.

Note that `game:squad` carries no `communityId`. That suggests an account belongs to a
single community, which matches how the accounts we have seen behave.

### Two lifetimes, kept apart

| Data | Strategy | Why |
| --- | --- | --- |
| `_links`, `userId`, `communityId` | Cached for the life of the process | Routing. It does not change. |
| `budget`, `teamValue`, `points`, `tactic`, counts | **Never cached** | A stale budget is a miscalculated bid |

No middle-ground TTL on the volatile half on purpose: a five-minute cache can still lie,
just unpredictably. Refetching costs one HTTP call; getting the money wrong costs a
signing.

### What we keep, and what we drop

The raw response carries the account email, an invitation code, Google advertising
identifiers, the community password field and moderation flags. **None of that belongs in
a conversation transcript.**

The models in `comunio/models.py` are therefore **allowlists, not filters**: only declared
fields survive validation, so a field Comunio adds tomorrow is dropped by default instead
of leaking. A test asserts the known-sensitive fields never appear in a serialised
snapshot.

Kept from `user`: `id`, `name`, `budget`, `teamValue`, `teamCount`, `teamCountLinedup`,
`points`, `salaries`, `tactic`.

Kept from `community`: `id`, `name`, and the subset of `rules` that constrains legal
moves — bidding mechanics (`second_highest_offers`, `anonymous_bidding`), market limits
(`tradables_on_exchangemarket`, `max_tradables_per_user`, `sales_ban`), squad constraints
(`players_member_per_club`), and pricing (`creditfactor`, `injured_tradable_offer_factor`,
buyout clauses).

`rules` looks like league metadata, but it is the rulebook the deterministic layer needs:
`second_highest_offers` alone changes what a correct bid amount is.

### Payload quirks

- **Numbers arrive as strings**: `"15000000"`, `"18"`. Pydantic coerces them; without the
  models, arithmetic would silently concatenate.
- **"No limit" is an empty string**, not `null` — `max_tradables_per_user: ""`. Handled by
  the `OptionalInt` validator.
- **Rules are wrapped**: the settings live under `community.rules.items`, not
  `community.rules`.
- URLs come with escaped slashes (`https:\/\/…`), which is valid JSON and decodes itself.

## The squad: `game:squad`

`/users/:userId/squad`, no community id — see the note above. Returns `items[]`, the
current `tactic`, and links to add or remove a player from the market. Those two write
endpoints are documented under [Write endpoints](#write-endpoints) and are reached through
the market link rather than from here.

Per player it carries availability, scoring, prices, lineup state and the next fixture.
`status` is `ACTIVE` or something like `WEAKENED`, with `statusInfo` naming the injury.
`nextMatch.kickoff` is a timezone-aware timestamp, and it is the only thing in the API
that says when a lineup stops being changeable. It is passed through as it arrives; working
out what to do about the deadline is the client's.

### "No data" is encoded five different ways

In a single response:

| Field | Encoding | Notes |
| --- | --- | --- |
| `points` | `"-"` | A dash string, not null |
| `lastPoints` | `null` or `"4"` | Differs between players in the same response |
| `averagePoints` | `"0"` or `3.5` | **String in one row, number in another** |
| `recommendedprice` | `-1` | Sentinel, not a price |
| `pos` | `""` | Empty until the player is lined up |

`MissingInt`, `MissingFloat`, `MissingStr` and `SentinelInt` in `models.py` normalise all
of these to `null`. Treating `-1` as a price or `"-"` as a number would poison any
arithmetic downstream, which is precisely the kind of error the deterministic layer exists
to avoid.

### Rival squads: same endpoint, different id

`/users/:userId/squad` takes any manager's id, so a rival's squad is the same call.
Everything is visible — prices, injuries, depth, and their lineup and formation once they
have set one. Two differences:

- `recommendedprice` is `-1` for every player. Comunio only suggests a price for players
  you own.
- A rival who has not set a lineup yet shows `linedup: false` throughout, which is
  indistinguishable from having no lineup at all.

Squad values cross-check against `teamValue` in the standings.

### `status` is an open set

Four values seen so far, and there is no reason to think that is all of them:

| Value | Meaning |
| --- | --- |
| `ACTIVE` | Available |
| `WEAKENED` | Carrying a knock, `statusInfo` names it |
| `INJURED` | Injured, `statusInfo` names it |
| `RED_BANNED` | Suspended after a red card |

Modelled as a plain string rather than a closed enum, so a fifth value does not break
validation. `summary.unavailable` counts everything that is not `ACTIVE`.

### Other observations

- `owner` is repeated identically on every player. The model hoists it to the top level.
- Roughly half of each player object is `_links` for logos, photos and watchlist actions.
- `nextMatch` is `null` for players whose fixture is not scheduled yet.

## Standings: `game:standings`

**Requires query parameters**: `?period=total&wpe=true`. Without them the response is not
JSON at all, which is why a bare `GET` on the link fails in a confusing way. `Session.link()`
does not need to know about this: parameters go to the client, which passes them straight
to httpx.

`wpe` is undocumented — the web app always sends it and the endpoint needs it.

### `period` changes which fields are real, not just which numbers

Two values are known: `total`, the season table, and `live`, the same table recomputed
for the matchday in progress. Three fields come back empty under `total` and only carry
data under `live`:

| Field | `total` | `live` |
| --- | --- | --- |
| `livePoints` | `null` | Points being scored right now |
| `playersPossiblyScoredAmount` | `0` | Players who may still score |
| `negativeBudget` | `false` for every row | True for the managers in the red |

`negativeBudget` is the one that matters. It is not that `total` omits it — it reports
`false` for managers who *are* overdrawn, which reads as a fact rather than as a gap.
Observed on a live league: one manager came back `false` under `total` and `true` under
`live` in the same minute, with no transfer between the two calls.

### Under `live`, numeric fields arrive present but null

`total` sends whole numbers for `totalPoints`, `totalPerennialPoints`,
`playersPossiblyScoredAmount` and `teamValue`. Under `live` the same keys can come back
**present with a `null` value** — `totalPerennialPoints` does so for every row on a
league with no carried-over points.

The distinction matters when parsing: `payload.get("totalPerennialPoints", 0)` returns
`None` here, because a `dict.get` default only fires when the key is *missing*, not when
it is present and null. Reading these with `... or 0` is what keeps a null out of a
field the model types as `int`.

Do not treat it as a field that is sometimes absent, and do not widen the model to
accept `None`: a null here means zero, and the table is more useful with the zero.

### `_embedded`, a shape the index does not use

Each row keeps the figures at the top and nests the manager and their team underneath:

```
items[]
├── totalPoints, lastPoints, livePoints, totalPerennialPoints, playersPossiblyScoredAmount
└── _embedded
    ├── user       → id, name, negativeBudget, position, plus login/firstName/flags
    └── teamInfo   → teamValue, tactic, badges, and a game:squad link for that rival
```

The model flattens both into a single row.

### Rank is not in the payload

Every `position` is `0`, so the field is useless and rank comes from the order Comunio
sends. Observed before the season starts: with all managers on zero points the order
follows squad value, so the ordering is doing tie-breaking of its own.

`lastPoints` is `"-"` here too, and `livePoints` is null outside a live matchday.

### Third-party data

Rival rows carry `login`, `firstName` and account flags belonging to other people. Only
what a table needs survives: display name, the figures, and the id needed to fetch their
squad. Fixtures invent the rivals.

Two fields are genuinely useful for market strategy: **`negativeBudget`** tells you which
rivals cannot outbid you, and each rival's **`teamValue`** comes with a link to inspect
their squad.

## The market: `game:exchangemarket`

**Not `game:tradables`.** That link points at a different collection and comes back empty
here; the market the web app shows is `game:exchangemarket`, at
`/communities/{communityId}/users/{userId}/exchangemarket`.

Each listing is HAL with `_embedded`, holding the player and the seller:

```
items[]
├── date, remaining, watched
└── _embedded
    ├── player → id, name, club, position, trend, quotedPrice, recommendedPrice,
    │            status, statusInfo, points, purchasePrice
    └── owner  → id, name, communityId
```

Top level also carries **`nextTransfersDateTime`**, when the current transfer round is
processed, and `dailyTransfersProcessed`.

### Seller id 1 is Comunio itself

Listings owned by user id `1`, named `Computer`, are put up by the game rather than by a
rival. That is a different proposition — nobody is negotiating, and no rival is deprived
of a player — so it is surfaced as `from_computer` instead of leaving an agent to
recognise the magic id. Listings owned by the signed-in manager are flagged `is_mine`,
since those are not buyable.

### Two traps

- **`quotedPrice` and `recommendedPrice` are capitalised here**, while the squad endpoint
  spells the same concepts `quotedprice` and `recommendedprice`. The aliases are not
  interchangeable, and reusing the squad model here would silently drop both prices.
- **`date` uses an offset with no colon** (`2026-08-10T04:15:06+0200`), unlike the
  `+02:00` seen elsewhere. Python parses both, but a hand-rolled parser would not.

`trend` is a small signed integer for price movement. It appears here and not in the squad
endpoint.

### Write endpoints

The response links to `game:exchangemarket:placeoffers` (`/offers`), `addplayer`,
`removeplayer` and `updateRecommendedPrice`. All four are in use: `list_player_on_market`,
`unlist_player_from_market`, `change_listing_price` and `place_bid` respectively. Note that
the path for the third is `/recommendedprice` even though it sets the manager's own asking
price — see [tools.md](tools.md).

## Offers: `game:readOffers`

**Returns HTTP 500 without `?current`.** It is a *valueless* query flag — `?current`, not
`?current=true` — so it is appended to the URL rather than passed as a parameter. A plain
GET on the link looks like a broken endpoint; it is not.

```
credit, hasMore
items[]
├── id, type, state, price, exchange, datecreated, datechanged
├── tradable         → the player, with quotedPrice / recommendedPrice
├── user             → who made the offer
├── tradingPartner   → the manager on the other side
└── _links           → game:offer:decline, game:offer:withdraw
```

### `credit` is not `budget`

The index reports a budget; this endpoint reports **credit**, and they differ. The league's
`creditfactor: "dynamic"` rule means spending power exceeds cash in hand. Sizing a bid
against the budget would understate what is actually possible, so `credit` is what
`get_offers` surfaces and what a bid should be measured against.

### Direction has to be derived

Nothing in an offer says whether it is incoming or outgoing. It comes from comparing
`user.id` — who made the offer — with the signed-in manager: their own id means outgoing,
anyone else means somebody wants one of their players.

### Offers are not always generous

`price` against the player's `quotedPrice` is the whole point of reading this endpoint, and
the difference goes both ways: observed premiums ranged from **−2.8 % to +3.8 %** in a
single response, all from the computer. `premium` and `premium_pct` are computed so nobody
accepts a below-value offer by assuming an offer is a good one.

### Quirks

- **`onWatchlist` is a boolean sent as the string `"false"`**, while the same concept is a
  real boolean named `watched` in the squad and market endpoints.
- **`points` is `0` here**, an integer, where the squad and market endpoints send the
  string `"-"` for the same "no data" state.
- Some manager names carry a **trailing space**. They are stripped.

### Write endpoints

Each offer links `game:offer:decline` and `game:offer:withdraw`, and the collection links
`game:placeOffers`. `withdraw_bid`, `accept_offer` and `change_bid` use them.

**`decline` and `withdraw` resolve to the same path with the same body.** Nothing in an
offer id says which of the two a call would perform, so the tool has to look the offer up
first: sent against somebody else's offer, a withdrawal declines it instead.

## Settled transfers: `game:readOffersHistory`

`/communities/:communityId/users/:userId/offers/history?offset=&limit=` — the settled half
of the collection `game:readOffers` serves while offers are still open. Same item shape,
every row `state: PROCESSED`, and `credit` comes back `null` rather than a figure.

**It honours the limit it is given.** Measured on a real league at 20, 50, 100 and 200: the
first returned 20 with `hasMore: true`, the rest returned all 31 there were with
`hasMore: false`. Pagination is `offset`, not `start`.

### `type` does not give the direction

Each item has `type: SALE | PURCHASE`, and it cannot be used to tell which way a player
moved. Over one league's whole history, `SALE` appeared **15 times on a player moving to
Comunio and 13 times on one moving from it**.

What holds, verified on 31 of 31 deals against the same ones in the news feed:

| Field | Is |
| --- | --- |
| `tradable.owner` | Who held the player — the seller |
| `user` | Whose offer it was — the buyer |
| `tradingPartner` | Repeats `tradable.owner` |

### Measured against the news feed

The same 31 movements over the same five days, day by day (5 / 5 / 5 / 11 / 5), and the
derived direction matches the feed's `FROM_COMPUTER` / `TO_COMPUTER` buckets exactly: 16
and 15.

| | Movements | Requests |
| --- | --- | --- |
| `game:readOffersHistory` | 31 | **1** |
| `game:news` | 31 | 12 |

It also carries what the digest does not: `quotedPrice` at settlement, the player's club,
position and status, the offer id, and both `datecreated` and `datechanged` where the
digest gives only the day it ran.

### Why it is worth reading

These are **settled prices**. The market says what a player is listed at; this says what
one actually went for, with the valuation beside it. Observed in one league: 31 transfers
totalling over 115 million, 15 of them paid above the player's quoted price.

**One caveat.** The league measured had been reset five days earlier, so both sources
bottom out in the same place. Whether the offer history reaches as far back as the feed in
a league with months behind it is not established.

## The league feed: `game:news`

No longer the source for transfers — it backs `get_news` alone. Completed transfers do
still arrive in it as **one entry per day**, mixed in with promotional HTML, welcome
messages and administration notices; `get_news` reports only how many moves such an entry
covers, since `get_transfers` owns that detail properly now.

### Parameters, measured rather than copied

The web app sends `group=true&originaltypes=true&start=0&limit=50&type=HIDDEN_NEWS`. What
each one actually does:

| Parameter | Effect |
| --- | --- |
| `originaltypes=true` | **Load-bearing.** Without it types collapse to coarse ones — `TRANSACTION` instead of `TRANSACTION_TRANSFER` — and entries cannot be told apart. |
| `group=true` | Nests entries under date keys instead of a flat `entries` list. More work to undo, so it is not sent. |
| `start`, `limit` | Pagination. **The server caps a page at 20** however large a limit is requested; `start` works as expected. |
| `type=HIDDEN_NEWS` | Measured to change nothing at all. Not sent. |

Filtering by type is not available server-side: passing `type=TRANSACTION_TRANSFER` returns
everything anyway.

### Shape

A transfer entry's `message` is bucketed by kind:

```
message
├── FROM_COMPUTER []  → bought from Comunio
└── TO_COMPUTER   []  → sold back to Comunio
    each: tradable {id,name}, from {id,name}, to {id,name}, price,
          and immediateTransferTime on sales that did not wait for the round
```

Only those two buckets have been observed, in a league whose market has so far been
computer-only. Manager-to-manager deals presumably arrive under a third key, so `get_news`
**counts whatever buckets are present** rather than naming them — undercounting a day's
transfers would be worse than not knowing the key's name.

`message` is **polymorphic across entry types**, which is why `get_news` has type-specific
fields that are null on the kinds they do not apply to:

| Type | `message` shape | Reduced to |
| --- | --- | --- |
| `TRANSACTION_TRANSFER` | Buckets of moves, as above | `transfers`, a count |
| `SYSTEM_ADMINISTRATION` | `{text, links}`, the text being HTML | `text` as plain text, plus `links` |
| `COMMUNITY_ADMINISTRATION` | `{text, links}` with **`text` empty** — the announcement is in the entry's `title` | `title` |
| `MEMBER_ADMINISTRATION` | `{text, links}`, plain already | `text` |
| `LINEUP_CHANGED` | The whole eleven, each player with club, club logo URL and photo URL, plus four substitute slots and `incomplete`, `tactic`, `promotion` | `tactic`, `lineup_incomplete` |

Prediction notices carrying `{type, matchday, eventId}` have also been seen. The type list
is **open**, so an unrecognised entry is returned with its type rather than dropped.

### The envelope every entry carries

`id`, `date`, `lastEdit`, `type`, `title`, `owner`, `recipient`, `comments`, `sticky`,
`poll`, `partner`, and `_links` with hrefs for `createComment` and `setSticky`. The links
and the `owner`/`recipient` pair are dropped; `comments` becomes a count.

### Bodies are HTML

Announcement text arrives as markup — tags, `<br />`, and an entity per accent
(`&iexcl;`, `&aacute;`). `get_news` strips tags **before** unescaping entities, so an
`&lt;` in the copy cannot become a tag that the stripper then removes.

## The watchlist: `game:watchlist`

`/communities/:communityId/users/:userId/watchlist`. A shortlist of players being kept an
eye on; it holds no money and changes nothing about the squad.

### Entries are under `tradables`, not `items`

Every other collection in this API returns `items[]`. This one returns `tradables[]`, and
its entries are **flat** — no `_embedded`, no nesting — unlike the market's.

### `owner` is null when nobody holds the player

The one field worth reading closely. A watched player with `owner: null` is unowned and
can only ever arrive through the market; one whose `owner` is a manager needs a deal or a
buyout clause. `get_watchlist` surfaces this per player as `unowned` and counts it.

### `quotedprice`, lowercase

The squad's spelling, not the market's `quotedPrice`. Third variant of the same concept
across four endpoints — see [Four spellings of one field](#four-spellings-of-one-field).

### Three operations, one path

| | Method | Body | Response |
| --- | --- | --- | --- |
| Read | `GET …/watchlist` | — | `{"tradables": [...]}` |
| Add | `POST …/watchlist/players/{id}` | **empty** `{}` | fifteen bytes; a bare `true` would not be out of character |
| Remove | `DELETE …/watchlist/players/{id}` | **also `{}`** | a status object |

Two things here are worth stating rather than rediscovering. **The `DELETE` carries a JSON
body**, which is unusual enough that `ComunioClient.delete` exists specifically to send
one. And **add and remove do not answer in the same shape**, so `_accepted()` treats both
`{"status": "OK"}` and a bare `true` as success.

Like every other write, neither is retried after a 401.

## Player detail: `game:tradable`

`/communities/:communityId/users/:userId/players/:playerId` — the `detailedInfo` link that
squad and market responses hang off every player. About 4 KB of data, same Bearer token as
everything else.

### Not the web app's player page

The page at `www.comunio.es` fetches a Next.js data route:
`/_next/data/<buildId>/es/laliga/<club>/<player>.json`. Avoid it:

- `<buildId>` changes on **every deploy** of the web app, so any URL containing it rots.
- It authenticates with cookies, not the Bearer token.
- The response is dominated by several thousand UI translation strings; the player data is
  a small fraction of it.

`game:tradable` returns the same information with none of those problems.

### What it adds over the squad

| Field | Why it matters |
| --- | --- |
| `historical.points[]` | Points **season by season**, fourteen of them in one observed response. Oldest first. |
| `buyoutClauseInfo.price` | What taking the player from their owner without consent would cost. `0` when the league has clauses disabled. |
| `purchaseInfo` | What the current owner paid, and when |
| `nextMatches[]` | The next **three** fixtures, where the squad gives one |
| `general` and `cards` | Goals, penalties, man-of-the-match awards, and the three card counts |
| `average.lastXMatchdays` | A recent-form window, blank until matches are graded |

Notably absent: `position`. It is in the squad and market payloads but not here.

`externalLinks` carries forum, blog and stats URLs, which are dropped.

## The full `status` vocabulary

The API sends bare codes. The complete set was recovered from the web app's own
translation table, and there are **thirteen**, not the four the API had happened to show:

```
ACTIVE            AWAY               DECEASED        GAME_BREAK
INJURED           MISCELLANEOUS      RED_BANNED      REHABILITATION
RETIRED           SUSPENDED          WEAKENED        YELLOW_BANNED
YELLOW_RED_BANNED
```

Each also has a `WAS_*` form for a state the player has come out of.

Three of them — `YELLOW_BANNED`, `YELLOW_RED_BANNED`, `SUSPENDED` — mean a player cannot be
fielded and would never have been guessed from a code alone. `comunio/statuses.py` maps
codes to plain language, handles the `WAS_` prefix by rule, and returns `None` for
anything unrecognised: it is a lookup, not a validator, and `status` stays a plain string
everywhere.

## Write endpoints

Captured from the web app, all six verified against a real account. **Nothing in this
project calls any of them.** They are written down so the execute layer can be built from
facts rather than guesses, and because several of the details below are the kind that
cause silent, expensive bugs.

| Action | Method | Path | Body |
| --- | --- | --- | --- |
| List a player | POST | `…/exchangemarket/addplayer` | `{"items":[{"tradableId":N,"price":N}]}` |
| Change asking price | PUT | `…/exchangemarket/recommendedprice` | `{"playerId":N,"newPrice":N}` |
| Unlist a player | POST | `…/exchangemarket/removeplayer` | `{"tradableIds":[N]}` |
| Place a bid | POST | `…/offers` | `{"offers":[{"price":N,"tradableid":N,"type":"NEW"}]}` |
| Change a bid | POST | `…/offers` | `{"offers":[{"offerid":N,"tradableid":N,"price":N,"type":"CHANGE"}]}` |
| Accept an offer | POST | `…/offers` | `{"offers":[{"offerid":N,"tradableid":N,"price":N,"type":"ACCEPT"}]}` |
| Withdraw an offer | PUT | `…/offers/{offerId}` | `{}` |

### One route, four meanings

`POST …/offers` places a bid, changes one, accepts an offer and — presumably — declines
one, told apart only by `type`:

| `type` | Meaning | `offerid` in the request | Applied |
| --- | --- | --- | --- |
| `NEW` | Place a bid | no, and the response returns the new one | queued |
| `CHANGE` | Change an existing bid's price | yes | queued |
| `ACCEPT` | Accept an offer for your player | yes | **immediately** |
| *not captured* | Decline an offer | — | — |

The value for declining is unknown. The offers payload links `game:offer:decline` and
`game:offer:withdraw` at the same `…/offers/{offerId}` path, where a `PUT` with an empty
body withdraws.

So the most dangerous action in the API shares a route with the most routine one, and a
wrong `type` is still a well-formed request. Nothing distinguishes them but a string.

### The asymmetry that matters most

| | Placing a bid | Accepting an offer |
| --- | --- | --- |
| `processImmediately` | `false` | **`true`** |
| Effect | Queued until the transfer round | **Applied instantly** |
| Reversible | Yes, by withdrawing | **No** |

Accepting is irreversible the moment the request returns. Any confirmation shown before
accepting has to be stronger than the one before bidding, because there is nothing to undo
it with.

A bid returns the new `offerid` in its response — that is the only way to get the handle
needed to change or withdraw it later. `CHANGE` and `ACCEPT` both require that handle;
only `NEW` goes without one.

### Two levels of status, and only one of them is trustworthy

```json
{"status":"OK",
 "response":[{"offerid":…,"status":"OK","message":"","processImmediately":false}],
 "opponentIds":""}
```

The outer `status` says the request was processed. The per-item `status` and `message` say
whether *that operation* worked. **An outer `OK` with a failed item inside is entirely
possible**, and reporting success from the outer field alone is how a tool ends up telling
someone a bid was placed when it was not.

`addplayer` expresses the same idea differently, with a `notPlaced` array listing the ones
that did not go through. Both are batch endpoints, so partial success is the normal case,
not an edge case.

### Four spellings of one field

The same player id, across four sibling endpoints:

```
addplayer            tradableId      (camelCase, inside items[])
recommendedprice     playerId        (a different word entirely)
removeplayer         tradableIds     (plural array)
offers               tradableid      (all lowercase)
```

Send `playerId` where `tradableid` is expected and the request is still well-formed JSON.

### Responses have no common shape

`{"status":"OK","notPlaced":[],"purchasePrices":{…},"remaining":36}`, then a bare `true`,
then `{"status":"OK"}`, then the two-level object above. There is no envelope to parse
generically: **each action needs its own request and response model.**

### Never auto-retry these

`ComunioClient` retries once on a 401. That is safe for `GET` and dangerous for everything
here: if a write reaches Comunio, takes effect, and the response is lost, a retry applies
it twice — a bid placed twice, a player listed twice. When `post()` and `put()` are added,
the retry must not cover them.

### Still unknown

- The `type` value for declining an offer. Three of the four are known: `NEW`, `CHANGE`,
  `ACCEPT`.
- Whether `decline` and `withdraw`, which share a path, differ by method or by who owns
  the offer.

  These two are the only unknowns that could touch **somebody else's** offer rather than
  the manager's own account, so they are worth being explicit about. Neither is reachable
  today: **no tool declines an offer**, and `withdraw_bid` looks the offer up first and
  refuses anything whose `direction` is not `outgoing` before a request is sent
  (`comunio/actions.py`). They are a gap in what is *mapped*, not an open path in what
  can be *called* — and mapping them means declining a real offer to watch what goes over
  the wire, which is not something to do casually. A `decline_offer` tool cannot be built
  until they are answered.
- What `remaining: 36` counts in the `addplayer` response. Market listings carry their own
  `remaining: 14`, so the two are not the same thing.
- What `opponentIds` is for; it has only ever come back as an empty string.
- Whether any of these are idempotent, and what a rejected bid looks like when credit is
  insufficient.

## How this is wired up

| Piece | Responsibility |
| --- | --- |
| `config.py` | Credentials and timezone from the environment; computes `tzoffset` |
| `comunio/auth.py` | Holds a usable token: logs in, refreshes, falls back to a full login if a refresh is rejected |
| `comunio/client.py` | Applies the token to every request and retries once on a 401 |
| `comunio/session.py` | Fetches `GET /`; caches routing, resolves named links, returns fresh state |
| `comunio/models.py` | Allowlist models for what Comunio returns |
| `context.py` | Builds the shared HTTP client and session once per process |

Design points worth keeping:

- **There is no `login` tool, and there will not be one.** Tools are model-controlled: a
  `login` tool would let the model authenticate whenever it felt like it, and its response
  would land in the model's context. Authentication sits underneath the tools.
- **Tokens never leave the process.** They are not returned by tools, not logged, not
  written to disk. Error messages carry the HTTP status only, because the response body of
  a failed login can echo the credentials back.
- **Tokens live in memory.** MCP is a stateless *protocol*, but the server process stays
  alive between calls, so there is no reason to put a rotating secret on disk.
- **A 401 is retried exactly once**, after dropping the cached token. Twice would risk
  hammering the login endpoint.

## Verifying it against the real API

Every test in the suite uses a mock transport, so **nothing in CI touches the real API**.
The `auth-check` script is what reaches it:

```bash
cp .env.example .env    # fill in your credentials
docker compose run --rm auth-check
```

It performs a login and a refresh and reports how long the token lasts. It prints no
token.

It exists to answer questions a mock cannot: whether the credentials work, whether the
headers get through, and whether the refresh really needs its `authorization` header.

It was originally written as a stand-in until a read tool existed, and `get_account` is
that now — but it is **kept** rather than deleted, because the two answer different
questions. Reaching `get_account` means an MCP client, a model and a conversation;
reaching this means a shell. When a login fails, it is the shortest path to the cause
with the least in the way to be wrong.

## Verified against the real API

On 2026-08-10, `auth-check` ran against `api.comunio.es` with real credentials:

```
Timezone Europe/Madrid, tzoffset 2
POST https://api.comunio.es/login "HTTP/1.1 200 OK"   → Login OK
POST https://api.comunio.es/login "HTTP/1.1 200 OK"   → Refresh OK
Access token valid for another 1799s
```

So the headers pass, the computed `tzoffset` is accepted, the refresh works with a rotated
token, and `expires_in: 1800` matches what the token actually reports.

On 2026-08-10, `get_account` was called end to end through the MCP stdio transport
against the real API and returned the live budget, squad totals, formation and league
rules.

## Not yet known

- The response shape of the routes **not documented above**. Nine are mapped —
  the index, squad, standings, market, offers, offer history, news, player detail and the
  write endpoints — out of the roughly ninety names in `_links`. The rest are known only
  as routes.
- Whether the `authorization` header is *required* on a refresh. We send it because the
  web app does, and it works; refreshing without it has not been tried.
- Which of the browser headers are load-bearing. The full set works; no subset has been
  tested.
- Rate limits, and what Comunio does about repeated failed logins.
