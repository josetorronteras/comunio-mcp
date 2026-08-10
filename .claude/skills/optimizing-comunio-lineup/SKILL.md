---
name: optimizing-comunio-lineup
description: Builds and applies an optimal Comunio fantasy-football starting lineup using the comunio MCP server's propose_lineup and execute_lineup tools. Use when the user asks to set, fix, optimize, or check their Comunio lineup, formation, or starting eleven, or mentions empty lineup slots or the lineup deadline.
---

# Optimizing a Comunio lineup

Comunio deducts 4 points for every empty lineup slot. `comunio:propose_lineup` computes the
best starting eleven deterministically — this skill only orchestrates showing it to the
user and applying it. Never pick players by hand; always go through the tools below.

## Workflow

Copy this checklist and track progress:

```
- [ ] 1. Check current squad and account
- [ ] 2. Propose a lineup
- [ ] 3. Present it and get explicit approval
- [ ] 4. Execute only after approval
- [ ] 5. Report the real result
```

**1. Check current state**

Call `comunio:get_squad` (and `comunio:get_account` if the current tactic or budget is
relevant). Read-only, always safe to call.

**2. Propose**

Call `comunio:propose_lineup`. Leave `tactic` unset unless the user asked for a specific
formation — the tool tries all five Comunio accepts (442, 343, 352, 433, 451) and picks the
one with the highest points net of the empty-slot penalty. This never changes the manager's
team: `propose_lineup` never calls a Comunio write endpoint.

**3. Present and confirm**

Show the user, from the response: `tactic`, each starter with their `average_points`,
`empty_slots` and what they cost (`estimated_penalty_points`), and any starter whose
`status` is not `ACTIVE` (used as a fallback because their position was short on available
players). Ask an explicit yes/no. Do not proceed without it — an approval dialog from the
host is not a substitute for this step.

**4. Execute**

Only on explicit approval, call `comunio:execute_lineup` with the `proposal_id` from step
2. Never call it speculatively or to "see what happens" — it replaces the real lineup on
the real account and cannot be undone by calling it again.

**5. Report**

Report `ok`, `fielded`, `empty_slots`, `penalty_points` and `unavailable` from the result.
Don't assume success just because the call returned — check `ok`.

## Rules

- Never compute or invent a lineup yourself; the optimization is deterministic server code,
  not something to reason about here.
- A proposal expires 30 minutes after being made. If the user takes longer to decide, call
  `comunio:propose_lineup` again rather than reusing a stale `proposal_id`.
- This changes the manager's real Comunio account. Step 3's confirmation is mandatory, not
  optional, even if the host also shows its own approval dialog.
