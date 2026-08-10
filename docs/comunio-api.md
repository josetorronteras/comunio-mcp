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
game:squad                  game:lineup              game:tradables      (the market)
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
Until there is a read tool to exercise, this script is the only thing that does:

```bash
cp .env.example .env    # fill in your credentials
docker compose run --rm auth-check
```

It performs a login and a refresh and reports how long the token lasts. It prints no
token.

It exists to answer questions a mock cannot: whether the credentials work, whether the
headers get through, and whether the refresh really needs its `authorization` header.
**Once a real read tool exists it becomes redundant and should be deleted.**

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

- The *response shape* of every endpoint other than `/login` and `/`. The routes are all
  known from `_links`; what they return is not.
- Whether the `authorization` header is *required* on a refresh. We send it because the
  web app does, and it works; refreshing without it has not been tried.
- Which of the browser headers are load-bearing. The full set works; no subset has been
  tested.
- Rate limits, and what Comunio does about repeated failed logins.
