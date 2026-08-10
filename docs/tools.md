# MCP tool catalogue

Every tool the server exposes, its layer and its effects. A tool is documented here in the
same change that implements it.

Layers are defined in [architecture.md](architecture.md): **read** never mutates,
**propose** computes a candidate without sending anything, **execute** applies a proposal
the user has already approved.

| Tool | Layer | Arguments | Returns |
| --- | --- | --- | --- |
| `ping` | read | — | Server name, version and UTC time |
| `get_account` | read | — | Budget, squad totals, formation and league rules |
| `get_squad` | read | — | Every player, with availability, scoring, prices and lineup state |

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

**`tactic`** and **`owner`** at the top level. `owner` appears once rather than repeated on
all fifteen players.

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
