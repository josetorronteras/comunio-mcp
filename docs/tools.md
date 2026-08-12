# MCP tool catalogue

Every tool the server exposes, its kind and its effects. A tool is documented here in the
same change that implements it.

Every tool named `get_*` only reads and is always safe to call. Everything else changes
the manager's team or spends their money, and is marked `read_only_hint=False` so a client
can tell them apart and ask before running one.

| Tool | Kind | Arguments | Returns |
| --- | --- | --- | --- |
| `get_account` | read | — | Budget, squad totals, formation and league rules |
| `get_squad` | read | `manager_id?` | Every player in a squad — the manager's own, or a rival's |
| `get_standings` | read | — | The league table, with rival squad values and who is broke |
| `get_market` | read | — | Every player up for sale, with prices, trend and seller |
| `get_offers` | read | — | Open offers in both directions, and real spending power |
| `get_transfers` | read | `limit?` | Completed transfers with the prices actually paid |
| `get_player` | read | `player_id` | One player's full detail sheet |
| `list_player_on_market` | **write** | `player_id`, `price` | Puts one of your players up for sale |
| `unlist_player_from_market` | **write** | `player_id` | Takes one of your players back off sale |
| `change_listing_price` | **write** | `player_id`, `price` | Changes what you are asking for a listed player |
| `place_bid` | **write** | `player_id`, `price` | Bids for a player on the market |
| `change_bid` | **write** | `offer_id`, `price` | Changes the amount of a bid you already placed |
| `withdraw_bid` | **write** | `offer_id` | Pulls one of your bids out of the running |
| `accept_offer` | **write, irreversible** | `offer_id` | Sells one of your players |
| `set_lineup` | **write** | `tactic`, players by position | Sets the formation and starting eleven |
| `get_watchlist` | read | — | Players being kept an eye on |
| `watch_player` | write | `player_id` | Adds a player to the watchlist |
| `unwatch_player` | write | `player_id` | Removes a player from the watchlist |

## `get_account`

The starting point for everything else. One call to Comunio's index endpoint returns:

**`account`** — `id`, `name`, `budget` (euros available to spend), `team_value`,
`team_count`, `team_count_linedup`, `points`, `salaries`, `tactic` (current formation).

**`community`** — `id`, `name`, and `rules`, the league settings that decide which moves
are legal:

| Rule | Why an agent needs it |
| --- | --- |
| `second_highest_offers` | If true, a winning bid pays the second-highest offer. Changes what a correct bid amount is. |
| `anonymous_bidding` | Whether rival bids are visible |
| `tradables_on_exchangemarket` | How many players the market holds |
| `max_tradables_per_user` | Cap on listings per manager, `null` when unlimited |
| `sales_ban`, `sales_ban_pro_offers` | Whether selling is currently blocked |
| `max_days_offers_are_pending` | When an offer expires |
| `players_member_per_club` | Cap on players from one club, `0` for no cap |
| `creditfactor` | How available credit is computed |
| `injured_tradable_offer_factor` | Price adjustment for injured players |
| `buyout_clause`, `buyout_clause_factor`, `buyout_clause_trade_lock` | The buyout route |
| `public_transaction_values` | Whether other managers' prices are visible |
| `salaries`, `members` | Whether salaries apply; league size |

Annotated `read_only_hint=True`. Never cached — the figures are fetched fresh on every
call, because a stale budget is a miscalculated bid.

Fails with a message naming the missing environment variables when credentials are not
configured.

### What it deliberately does not return

The underlying response carries the account email, an invitation code, Google identifiers,
the community password field and moderation flags. The models are allowlists, so those
never reach the model's context. See [comunio-api.md](comunio-api.md).

## `get_squad`

The richest endpoint, and what the lineup and market work builds on.

**Per player** — `id`, `name`, `club`, `position` (`keeper`, `defender`, `midfielder`,
`striker`), plus:

| Group | Fields |
| --- | --- |
| Availability | `status`, `status_info` (names the injury), `next_match` with its `kickoff` |
| Scoring | `points`, `last_points`, `average_points`, `matchday_points`, `motm` |
| Lineup | `linedup`, `substitute`, `lineup_slot` |
| Market | `quoted_price`, `recommended_price`, `on_market`, `is_exchangeable`, `has_accepted_offers`, `watched` |

**`summary`** — `total`, `lined_up`, `substitutes`, `unavailable`, `on_market` and
`by_position`. Computed server-side so nobody has to recount a list to check a formation.

**`tactic`**, **`owner`**, **`owner_id`** and **`is_mine`** at the top level. The owner
appears once rather than repeated on every player.

### Inspecting a rival

Pass `manager_id`, taken from `get_standings`, to read somebody else's squad. Rival squads
are fully visible: prices, injuries, depth, and their lineup once set. The one thing
missing is `recommended_price`, which Comunio only provides for your own players and sends
as `null` for everyone else.

Annotated `read_only_hint=True`.

### Values that are normalised on the way out

Comunio encodes "no data" five different ways in this one endpoint. The model returns
`null` for all of them, so the agent never has to know:

| Raw | Meaning | Returned as |
| --- | --- | --- |
| `points: "-"` | No points scored yet | `null` |
| `lastPoints: null` or `"4"` | Inconsistent between players | `null` or `4` |
| `averagePoints: "0"` or `3.5` | String in one row, number in another | `float` |
| `recommendedprice: -1` | Comunio has no recommendation | `null` |
| `pos: ""` | Not in the lineup | `null` |

`status` is an open set — `ACTIVE`, `WEAKENED`, `INJURED` and `RED_BANNED` seen so far —
so it stays a string. `summary.unavailable` counts everything that is not `ACTIVE`.

## `get_standings`

The league table, best first.

Per row: `rank`, `is_me`, `manager` and `manager_id`, `total_points`, `last_points`,
`live_points`, `perennial_points`, `players_possibly_scoring`, `team_value` and
`negative_budget`.

Two of those are market intelligence rather than trivia. **`negative_budget`** says which
rivals cannot outbid you right now. **`manager_id`** is what a rival-squad lookup will
need.

Annotated `read_only_hint=True`.

### Computed server-side

- **`rank`** — the payload's own `position` field is `0` for everyone, so rank is derived
  from the order Comunio returns.
- **`is_me`** — marks the signed-in manager's row, so the agent does not have to work out
  which one it is by matching names.

### Third-party data

Rival rows in the raw response carry `login`, `firstName` and account flags belonging to
other people. Only the display name, the figures and the id survive.

## `get_market`

Every player currently up for sale.

`closes_at` is when the current transfer round is processed — bids have to be in before
it. `daily_transfers_processed` says whether today's round has already run.

Per listing: `player_id`, `name`, `club`, `position`, `status` and `status_info`,
`quoted_price`, `recommended_price`, `trend`, `listed_at`, `remaining`, `watched`, and
three fields about the seller.

| Field | Meaning |
| --- | --- |
| `seller`, `seller_id` | Who is selling |
| `from_computer` | Listed by Comunio itself, not a rival. Nobody is negotiating. |
| `is_mine` | The manager's own listing, so not buyable |

`summary` splits the market by seller kind — `from_computer`, `from_managers`, `mine` —
plus `unavailable` and `by_position`.

Annotated `read_only_hint=True`.

### Computed server-side

`from_computer` comes from a reserved seller id of `1`, and `is_mine` from the session's
manager id. Neither should be left to an agent to recognise: one is a magic number, the
other is name matching.

## `get_offers`

Open transfer offers, and the number that actually bounds a bid.

**`credit`** is what the manager can spend. It is *not* the `budget` from `get_account`:
the league's dynamic credit factor lets it exceed cash in hand. Anything sizing a bid
should use this.

Per offer: `offer_id`, `type`, `state`, `price`, `created_at`, `changed_at`, `is_exchange`,
the `player`, and:

| Field | Meaning |
| --- | --- |
| `direction` | `incoming` when somebody wants the manager's player, `outgoing` when they are bidding |
| `premium`, `premium_pct` | Price against the player's market value. **Negative means below value.** |
| `offered_by`, `from_computer` | Who made the offer, and whether it was Comunio itself |
| `counterparty` | The manager on the other side |

`summary` gives `total`, `incoming`, `outgoing`, `from_computer`, `below_quoted`, and
`incoming_total` — what accepting every incoming offer would bring in.

Annotated `read_only_hint=True`. Accepting, declining and withdrawing are deliberately not
available here.

### Computed server-side

- **`direction`** — nothing in the payload states it; it comes from comparing the offer's
  author with the signed-in manager.
- **`premium` and `premium_pct`** — an offer is not automatically a good one. Real
  responses have carried premiums from -2.8% to +3.8% in the same batch.
- **`below_quoted`** — how many incoming offers are worth less than the player.

## `get_transfers`

Transfers that have already completed, newest first.

The point of this tool is **settled prices**. `get_market` says what a player is listed at;
this says what one actually went for, which is what a bid should be calibrated against.

Per transfer: `player`, `player_id`, `price`, `from_manager`, `to_manager`, `date`, and

| Field | Meaning |
| --- | --- |
| `from_computer` | Bought from Comunio |
| `to_computer` | Sold back to Comunio |
| `involves_me` | The signed-in manager was on one side |
| `kind` | The bucket Comunio filed it under |
| `immediate_at` | Clock time of a sale that did not wait for the transfer round |

`summary` totals each kind plus `total_value`.

`limit` defaults to one page of news. Larger values cost one extra request per page, so it
is worth raising only when the extra history is wanted.

Annotated `read_only_hint=True`.

### What it deliberately does not return

There is no transfers endpoint — these come out of the league news feed, which is mostly
promotional HTML, welcome messages and administration notices. All of that is dropped. A
single marketing entry in that feed is longer than every transfer in it put together, and
none of it belongs in a model's context.

## `get_player`

Everything Comunio knows about one player. Ids come from `get_squad`, `get_market` or
`get_offers`.

Beyond what the squad already gives:

| Field | Contents |
| --- | --- |
| `history` | Points season by season, oldest first — fourteen seasons in one real response |
| `record` | Matches played and rated, goals, penalties, man-of-the-match awards, all three card counts |
| `averages` | Season grade and points, plus a recent-form window |
| `buyout_clause` | What taking the player from their owner without consent would cost. `0` when the league has clauses off. |
| `purchase_price`, `purchased_on` | What the current owner paid |
| `next_matches` | The next three fixtures, where the squad gives one |
| `profile` | Date of birth, nationality, height, weight, foot, shirt number |

Annotated `read_only_hint=True`.

### Computed server-side

- **`status_meaning`** spells out the code. There are thirteen of them, and
  `YELLOW_RED_BANNED` is not something to leave an agent to interpret.
- **`available`** is true only for `ACTIVE`, so nothing has to know which of the other
  twelve codes mean the player cannot be fielded.

`position` is not in this payload — it comes from `get_squad` or `get_market`.

## `list_player_on_market`

**Changes the team.** Puts one of the manager's own players up for sale at the given asking
price.

| Annotation | Value | Why |
| --- | --- | --- |
| `read_only_hint` | `false` | It mutates |
| `destructive_hint` | `false` | Reversible — the player can be taken back off the market |
| `idempotent_hint` | `false` | Listing twice is not the same as listing once |

Ids come from `get_squad`. `get_player` gives Comunio's suggested price for comparison.

### Read the result, do not assume it

```json
{"placed": [3354], "rejected": [], "remaining": 36}
```

`addplayer` is a batch endpoint and reports per player. **Comunio can refuse an individual
player while reporting overall success**, so `placed` and `rejected` are read from
`notPlaced` rather than inferred from the outer `status`. `remaining` is Comunio's own
counter; what it counts is undocumented and does not match the countdown on market
listings.

### Not retried

Writes go through `ComunioClient.post`, which does not retry on a 401 the way `get` does.
A write that reached Comunio and lost only its response would be applied twice by a retry.
A 401 on a write is reported as a failure instead.

## `unlist_player_from_market`

**Changes the team.** Takes one of the manager's own players back off the market.

Ids come from `get_market`, where the manager's own listings are the ones marked
`is_mine`. Offers already received for that player are **not** cancelled by unlisting —
those live in `get_offers`.

Annotated the same way as listing: `read_only_hint=false`, `destructive_hint=false`
because listing puts it straight back, `idempotent_hint=false` because whether a repeated
call is a no-op is not something the response lets us verify.

### Comunio says less here than when listing

```json
{"status": "OK"}
```

That is the whole response. Where `addplayer` reports a `notPlaced` array, this reports
nothing per player, so `unlisted` is **what was asked for rather than what was
confirmed**. The model's description says so, and points at `get_market` for confirmation.

## `change_listing_price`

**Changes the team.** Changes what the manager is asking for a player they already have on
the market. The player must be listed first.

### The name is deliberate, twice over

Comunio calls this route `recommendedprice`, and the link `updateRecommendedPrice`. It does
**not** touch Comunio's recommendation — it sets the manager's own asking price. Naming the
tool after the route would have told the model it was adjusting the game's suggestion,
which is the opposite of what happens.

It is also not called `set_asking_price`, which was the first attempt: that name says
nothing about the player having to be **listed already**. "Listing price" does, and it
pairs with `list_player_on_market` and `unlist_player_from_market`. The `recommended_price` reported by `get_market` and
`get_player` is Comunio's own and cannot be changed.

### The odd one out, twice over

It is a **`PUT`** where the other market actions are `POST`s, and it answers with a **bare
`true`** rather than an object. There is nothing to read beyond whether it worked, so `ok`
is `payload is True` and anything else counts as failure.

This is also the only write action annotated `idempotent_hint=true`: setting the same price
twice leaves the same price. The others make no such claim, because their responses give no
way to verify it.

## `withdraw_bid`

**Changes what the manager has committed to.** Pulls one of their own pending bids.

Ids come from `get_offers`. Only offers whose `direction` is `outgoing` can be withdrawn.

### Guarded, because Comunio cannot tell the two apart

`game:offer:withdraw` and `game:offer:decline` point at the **same path**, and the request
is identical. Sent against somebody else's offer it would *decline* that offer rather than
withdraw one of the manager's bids — two very different outcomes from the same call.

Nothing in an offer id says which it is, so the tool looks the offer up first and refuses
anything that is not an outgoing bid **before any request is sent**. That costs one extra
read and removes a way to do the wrong thing by accident.

It also means the result can name what was withdrawn — the player and the amount — rather
than echoing an id back.

Annotated `destructive_hint=false`: the bid is gone, but a new one can be placed while the
market is open.

## `place_bid`

**Commits the manager's money.** Bids for a player on the market.

The bid does not take effect straight away: it waits for the next transfer round, which
`get_market` reports as `closes_at`. Until then `change_bid` and `withdraw_bid` can still
reach it. That is why it is annotated `destructive_hint=false`.

### Three refusals before anything is sent

| Refused when | Why |
| --- | --- |
| The player is not on the market | Nothing to bid on |
| The player is one of the manager's own listings | Not a move |
| The amount exceeds available **credit** | It cannot be paid |

The credit check reads `credit` from `get_offers`, **not** `budget` from `get_account`.
The league's credit factor makes them different numbers, and sizing a bid against the
budget understates what is possible.

It also subtracts the manager's **other open bids**, which Comunio's own `credit` does
not. Measured directly: placing a bid of 170,001 left `credit` reported as the same
29,749,200 it was before. Without accounting for them, five bids of ten million each
would every one pass a check against thirty million of credit. `credit_committed` says how
much is already promised, and `credit_after` assumes every open bid wins.

Changing a bid excludes the bid being changed, since the old amount is replaced rather
than added to.

Each refusal is tested by asserting no request left the process, not by the wording of the
error.

### Read `ok`, never the outer status

```json
{"status": "OK", "response": [{"status": "ERROR", "message": "Credit exceeded"}]}
```

Comunio reports the request as processed while rejecting the bid inside it. `ok` and
`message` come from the per-item status. `credit_after` only moves when the bid was
actually accepted.

### The offer id is the handle

`offer_id` in the result is the only way to reach the bid afterwards. Without keeping it,
a bid just placed can be neither changed nor withdrawn.

## `change_bid`

**Changes what the manager has committed.** Edits the amount of a bid already placed.

Ids come from `get_offers`; only `outgoing` offers can be changed. Like a new bid it waits
for the transfer round and can still be pulled with `withdraw_bid`, hence
`destructive_hint=false`.

### The player is not an argument

`tradableid` is taken from the offer being changed, not passed in. A change therefore
cannot end up pointing at a different player than the bid it edits — a mistake that would
otherwise be one wrong number away and invisible in the confirmation.

### The same three refusals

Unknown id, an offer *for* one of the manager's players rather than a bid of theirs, and
an amount beyond available credit. All refused before any request is sent, all tested by
asserting nothing left the process.

Whether `credit` already accounts for bids currently outstanding is not documented, so the
check compares against the figure as reported.

## `accept_offer`

**The only action here that cannot be undone.** Accepts an offer for one of the manager's
players, selling them.

Every other write queues or can be reversed: a bid waits for the transfer round and can be
withdrawn, a listing can be unlisted, a price can be set again. An acceptance comes back
with `processImmediately: true`. The player is gone the moment the call returns.

It is the only tool annotated **`destructive_hint=true`**.

### What the model is told to say first

The description requires two things to be stated before asking for agreement: **who** is
being sold, and **how the price compares to what the player is worth**. That second one is
`premium` and `premium_pct`, and it is in the result as well as in `get_offers`.

It matters because selling below value is common and invisible unless someone does the
subtraction. On the real account, three of ten open offers were below the player's quoted
price — and one of those was accepted for 3,300 less than the player was worth.

The tool does **not** refuse a below-value sale. That is a legitimate move and the
manager's call; the job here is to make sure it is a choice rather than an accident.

### Nothing is passed in but the id

The player and the price come from the offer itself. What is accepted is exactly what was
offered, and there is no argument to get wrong.

Only `incoming` offers can be accepted; accepting one of the manager's own bids is refused
before anything is sent.

## `set_lineup`

**Replaces the current lineup.** Sets the formation and the starting eleven.

Players are given **by position**, not by slot: `keeper`, `defenders`, `midfielders`,
`strikers`. Ids come from `get_squad`.

### The slot numbers are worked out here

Comunio's endpoint takes numbered slots `"1"` to `"11"` and never says what a number
means. The mapping was deduced by cross-referencing two real lineups against the squad —
in both a 442 and a 343 the keeper sat in slot 11 and a striker in slot 1. Slots fill from
the strikers backwards:

```
343 → 1,2,3 strikers · 4,5,6,7 midfielders · 8,9,10 defenders · 11 keeper
442 → 1,2   strikers · 3,4,5,6 midfielders · 7,8,9,10 defenders · 11 keeper
```

That arithmetic is exactly the kind of thing that does not belong in a prompt, so the tool
owns it. `slot_plan()` is tested directly.

Valid formations, read as defenders–midfielders–strikers: **442, 343, 352, 433, 451**.

### Incomplete lineups are allowed, and priced

Comunio does not refuse a half-filled lineup; its own interface warns that each empty slot
costs four points. So empty slots are permitted and the result reports `empty_slots` and
`penalty_points`. The four-point figure comes from Comunio's wording, not from a
measurement.

### Injured players are reported, not blocked

Comunio permits fielding someone who is injured or suspended, so the tool does too. They
come back in `unavailable` instead. Refusing would be inventing a rule the game does not
have.

### Refused before anything is sent

An unknown formation · more players than the formation has room for · a player not in the
squad · the same player twice · someone put in a position they do not play. Each is tested
by asserting nothing left the process.

Annotated `idempotent_hint=true` — sending the same lineup twice leaves the same lineup —
and `destructive_hint=false`, since it can be set again until the matchday starts.

## The watchlist: `get_watchlist`, `watch_player`, `unwatch_player`

A shortlist, not a commitment. Watching a player changes nothing about the squad, the
budget or any offer, which is why the two writes are annotated `destructive_hint=false`
and `idempotent_hint=true` — watching an already watched player leaves them watched.

### `owner` is the useful field

An entry carries `owner: null` when **no manager holds that player**. That is a real
distinction: an unowned player can only ever arrive through the market, while one held by
a rival needs a deal or a buyout clause. It is surfaced per player as `unowned` and
counted in the response.

### Three shapes on one path

| | Method | Body |
| --- | --- | --- |
| Read | `GET …/watchlist` | — |
| Add | `POST …/watchlist/players/{id}` | **empty** `{}` |
| Remove | `DELETE …/watchlist/players/{id}` | **also `{}`** |

A `DELETE` that carries a JSON body is unusual enough to be worth stating rather than
rediscovering. `ComunioClient.delete` exists for it, and like `post` and `put` it is never
retried.

### Spelling, again

This endpoint sends `quotedprice` — the squad's spelling, not the market's `quotedPrice`.
That is now the third variant of the same concept across four endpoints.
