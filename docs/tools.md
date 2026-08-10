# MCP tool catalogue

Every tool the server exposes, its layer and its effects. A tool is documented here in the
same change that implements it.

Every tool named `get_*` only reads and is always safe to call. Everything else changes
the manager's team or spends their money, and is marked `read_only_hint=False` so a client
can tell them apart and ask before running one.

| Tool | Layer | Arguments | Returns |
| --- | --- | --- | --- |
| `ping` | read | — | Server name, version and UTC time |
| `get_account` | read | — | Budget, squad totals, formation and league rules |
| `get_squad` | read | `manager_id?` | Every player in a squad — the manager's own, or a rival's |
| `get_standings` | read | — | The league table, with rival squad values and who is broke |
| `get_market` | read | — | Every player up for sale, with prices, trend and seller |
| `get_offers` | read | — | Open offers in both directions, and real spending power |
| `get_transfers` | read | `limit?` | Completed transfers with the prices actually paid |
| `get_player` | read | `player_id` | One player's full detail sheet |
| `list_player_on_market` | **write** | `player_id`, `price` | Puts one of your players up for sale |

## `ping`

Liveness check. Answers even when no credentials are configured, so it distinguishes "the
server is not running" from "the server cannot reach Comunio".

Annotated `read_only_hint=True`. Touches nothing.

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
