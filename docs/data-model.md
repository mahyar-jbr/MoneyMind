# Data Model

> All collections are namespaced by `user_id`. The demo seeds a single user; the schema generalizes.

## `transactions`

The raw operational ledger. Ingested from CSV.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  date: ISODate("2026-05-18"),
  merchant: "DoorDash",
  merchant_canonical: "doordash",      // normalized for grouping
  category: "food.delivery",
  amount: -38.42,                       // negative = outflow
  currency: "USD",
  source: "csv_import_2026-05-21_synthetic-csv_a1b2c3d4",
                                        // content-addressed: <date>_<filename-slug>_<sha256-prefix>.
                                        // Same bytes → same source → overwrite (idempotent re-upload).
                                        // Different bytes → new source → append (corrected re-upload).
                                        // Established by #11b after the demo cluster doubled.
  raw: { /* original CSV row */ }
}
```

Indexes: `{ user_id: 1, date: -1 }`, `{ user_id: 1, category: 1, date: -1 }`.

## `goals`

User-stated targets.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  title: "Emergency fund",
  target_amount: 8000,
  current_amount: 2400,
  target_date: ISODate("2026-12-31"),
  pace_check: "weekly",
  status: "active",       // active | paused | complete | abandoned
  created_at: ISODate(...),
  abandoned_at: null      // null while active; set to UTC datetime by abandon_goal
                          // when status flips to "abandoned". Never deleted — status flip only,
                          // so the agent retains the history ("you abandoned the gym-budget goal
                          // back in March").
}
```

## `user_context`

Things the user tells the agent. The "I'm bulking" layer.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  text: "I'm bulking this month, food spend will be high",
  type: "lifestyle",                    // lifestyle | event | preference | constraint
  active_from: ISODate("2026-05-01"),
  active_until: ISODate("2026-05-31"),  // null = ongoing
  created_at: ISODate(...)
}
```

The agent reads active context on every turn and weighs it before flagging anomalies.

**Active-on-date predicate (the contract):** any reader resolving "which contexts apply on date `T`?" — including the graph node in #11a, future dashboard widgets, the cron — must use this exact predicate to avoid drift:

```js
{
  user_id: <user>,
  active_from: { $lte: T },
  $or: [
    { active_until: null },
    { active_until: { $gte: T } },
  ],
}
```

Both bounds are inclusive (matches the codebase-wide date convention). `active_until: null` means ongoing. Established + verified live in `#15`'s demo script against real Atlas.

## `memories`

Patterns the agent discovers. **This is the magic collection.**

```js
{
  _id: ObjectId,
  user_id: "u_482",
  type: "pattern",                      // pattern | preference | reaction | fact
  tag: "food_spike→no_prep",
  summary: "Food delivery spikes correlate with work-stress / no meal prep",
  evidence: [
    { date: ISODate("2026-02-12"), note: "exam week, +$70 on DoorDash" },
    { date: ISODate("2026-05-18"), note: "busy work week, +$70 on DoorDash" }
  ],
  intervention: { sunday_reminder: true },
  confidence: 0.78,                     // 0–1, agent's self-reported certainty
  embedding: [/* 1024 dims; written explicitly on insert via Voyage (voyage-3), not auto-embed */],
  created_at: ISODate(...),
  last_used: ISODate(...),
  use_count: 3,
  deleted_at: null                      // V3 soft-delete. null while active; set to UTC datetime
                                        // by forget_memory when the user asks the agent to forget.
                                        // recall_memory filters out docs where deleted_at != null
                                        // so soft-deleted memories never surface in vector recall.
                                        // We never hard-delete — keeps the agent honest about what
                                        // it once knew, and forgetting is itself signal.
}
```

**Vector index:** `memories.embedding` — HNSW, 1024 dim, cosine. Recalled via `recall_memory(query, k=5)`.

## `budgets` (V6)

User-set per-category monthly spending caps. The agent reads active budgets when assessing whether a spend is concerning; the dashboard renders progress bars against them.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  category: "food",                     // top-level category: 'food' | 'shopping' | 'transport' |
                                        // 'entertainment' | 'bills' | ... (top-level, not the dotted
                                        // sub-category like 'food.delivery' used in transactions).
  limit: 400.00,                        // float > 0; the monthly cap in user currency.
  period: "month",                      // currently only 'month'; reserved for future 'week' | 'year'.
  status: "active",                     // 'active' | 'abandoned'
  created_at: ISODate(...),             // UTC, server-stamped on first insert; preserved across edits
  updated_at: ISODate(...)              // UTC, bumped on every set_budget upsert
}
```

**One ACTIVE budget per (user_id, category).** `set_budget` upserts — if an active budget exists for the same `(user_id, category)`, it edits the `limit` in place (preserves `created_at`, bumps `updated_at`). If none exists, it inserts a new doc with `status: "active"`. This is why there is no separate `edit_budget` tool: "create" and "edit" are the same intent from the user's perspective ("set my food budget to $400").

**`abandon_budget` flips `status` to `"abandoned"` — it never deletes.** Same reasoning as `goals.abandoned_at`: the agent retains the history ("you abandoned your food budget last month") and a future `set_budget` for the same category creates a fresh active doc rather than reviving the abandoned one. Readers querying "current budgets" filter on `{status: "active"}`.

## `interventions`

Proposed and accepted nudges. The full lifecycle is tracked so the agent can learn what works.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  proposed_at: ISODate(...),
  triggered_by: { tool: "get_spend_anomaly", input: {...} },
  type: "weekly_reminder",              // cap | reminder | swap_suggestion | reflection
  params: { day: "sunday", what: "meal prep" },
  user_response: "accepted",            // null at propose time; one of
                                        // accepted | declined | modified | ignored
                                        // after respond_to_intervention fires (#17a)
  responded_at: ISODate(...),           // null at propose time; UTC datetime once response lands
  related_memory: ObjectId,             // optional FK to memories._id; null when none
  status: "pending"                     // "pending" at propose time, "responded" or
                                        // "ignored" after respond_to_intervention. Indexable,
                                        // cheaper for readers than {user_response: null}.
                                        // Established by #17.
}
```

**Pending vs. answered:** `propose_intervention` (#17) writes the doc in PENDING form — `user_response: null`, `responded_at: null`, `status: "pending"`. The `respond_to_intervention` tool (#17a) sets the three response fields and flips `status` to `"responded"` (or `"ignored"` if a timeout path lands later). Readers querying "which interventions still need a user reply?" filter on `{status: "pending"}` — single indexable lookup.

## `outcomes`

Did the intervention work? Closes the learning loop.

```js
{
  _id: ObjectId,
  intervention_id: ObjectId,            // FK to interventions._id; stored as ObjectId, not string
  user_id: "u_482",
  measured_at: ISODate(...),            // UTC, server-stamped by log_outcome (#18)
  window_days: 14,
  metric: "weekly_food_spend",          // free-string; the agent chooses the unit
  before: 180.00,
  after: 118.50,
  delta_pct: -34.17,                    // SERVER-COMPUTED by #18, never agent-input.
                                        // (after - before) / abs(before) * 100, rounded to 2dp.
                                        // abs(before) so sign reflects direction-of-change for
                                        // negative-baseline metrics. before=0 → 0.0 deterministic.
  agent_judgment: "successful"          // successful | partial | failed | inconclusive
                                        // The AGENT's self-assessment, not the user's.
}
```

**Outcomes vs. interventions:** `log_outcome` (#18) writes the measurement; it does NOT mutate the corresponding intervention doc. The two collections are joined by `intervention_id` — readers compose, writers don't. The intervention/outcome relationship is 1:1 in spirit but unenforced by the schema (no unique index); the agent's prompt prevents double-logging.

Agent reads recent outcomes when proposing similar interventions in the future.

## `reminders`

One-off scheduled pings — user-requested ("remind me to cancel the gym trial in 7 days") or agent-self-scheduled ("checking back in on the bulking goal in 3 days"). **Distinct from interventions:** no approval flow, no outcome measurement, fires once. Established by `#19`.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  fires_at: ISODate(...),               // UTC INSTANT-IN-TIME (see "tz contract" below).
                                        // The moment the cron should fire this reminder.
  text: "cancel the gym trial",         // 3-200 chars; rendered verbatim by the delivery layer.
  source: "user",                       // "user" | "agent" — who scheduled it. Different framings
                                        //   downstream ("you asked me to..." vs. "checking in like
                                        //   I said I would..."), so the cron prompt branches.
  related_intervention_id: ObjectId,    // optional FK to interventions._id; null when not anchored
                                        //   to an intervention. Stored as ObjectId, not string.
  status: "pending",                    // "pending" | "fired" | "cancelled"
                                        //   pending: written by #19, awaiting fire
                                        //   fired:   set by the #21 cron at delivery
                                        //   cancelled: set by a future cancel_reminder tool
  created_at: ISODate(...),             // UTC, server-stamped by #19
  fired_at: null                        // null at write; UTC datetime set by #21 cron when fired
}
```

**Canonical "pending due by T" predicate (the contract):** the `#21` cron — and any future reader resolving "which reminders should fire by time T?" — must use this exact predicate to avoid drift:

```js
{
  user_id: <user>,
  status: "pending",
  fires_at: { $lte: T },
}
```

…sorted `{fires_at: 1}` for ordered processing. T is `datetime.now(UTC)` at cron tick. Established + verified live in `#19`'s demo script.

**Timezone contract (deliberate exception to architecture.md convention 5):** `fires_at` and `fired_at` are **UTC instants**, NOT calendar-day naive datetimes. The pipeline:

- Input is UTC-aware (or coerced from naive at the model validator)
- In-process `result.fires_at` IS UTC-aware
- Persisted doc reads back as tz-NAIVE at the same UTC wall-clock — pymongo strips tzinfo on store by default
- Comparisons (`{$lte: now}` with `now = datetime.now(UTC)`) still resolve correctly because both sides are at the same UTC wall-clock

The cron author does NOT need to special-case the naive read — `datetime.now(UTC)` vs. a naive UTC instant compares correctly under pymongo's default behavior. This is the same shape `transactions.date` and other date fields produce, but `fires_at` represents a moment in time rather than a calendar day. Reason for the exception: naive datetime + cron across timezones is a category of production bug we'd rather not invite.

**Interventions vs. reminders (the boundary):**

| | Interventions (`#17`) | Reminders (`#19`) |
|---|---|---|
| Trigger | Pattern-detected by the agent | User-requested OR agent self-scheduled |
| Approval | Yes — Accept / Decline / Modify | No — pre-accepted by intent |
| Outcome | Measured in `outcomes` (`#18`) | None — fires once, marked done |
| Cadence | Often recurring (weekly, monthly) | One-off |
| Schema | Carries `triggered_by`, `user_response`, `related_memory` | Carries `fires_at`, `source`, optional `related_intervention_id` |

When the agent observes a pattern AND wants a future ping anchored to the user's acceptance, both fire: `propose_intervention` for the pattern + `schedule_reminder` (with `related_intervention_id`) for the literal future ping.

## `inbox_messages`

The persistence layer for proactive notifications surfaced to the user outside an active chat turn. Written by the `weekly_summary` and `reminders` crons (the `POST /agent/run-weekly-summary` and `POST /agent/run-reminders` endpoints); rendered in the in-app inbox.

```js
{
  _id: ObjectId,
  user_id: "u_482",
  type: "weekly_summary",               // 'reminder' | 'weekly_summary'
  title: "Your week in spending",       // short headline rendered as the inbox row label
  body: "You spent $214 this week...",  // full message body, rendered when the user opens the item
  metadata: {                           // type-specific payload; free-shape per type.
    week_start: "2026-06-01"            //   weekly_summary: { week_start: "YYYY-MM-DD" }
                                        //   reminder: { reminder_id: ObjectId, source: "user"|"agent",
                                        //               related_intervention_id?: ObjectId }
  },
  created_at: ISODate(...)              // UTC, server-stamped by the cron at write time;
                                        //   the inbox sorts by this field descending.
}
```

**Why a separate collection (not just `reminders` + `interventions` in the UI):** the inbox is a read model. The cron is the writer; the agent's tools are NOT. `reminders` carries scheduling state (`fires_at`, `status: pending|fired|cancelled`) and `interventions` carries lifecycle state (`status: pending|responded`) — conflating those with "what does the user see in their inbox right now?" forces the frontend to understand both schemas. `inbox_messages` is the flattened, render-ready projection: one row, one card.

**Cron → inbox flow:**
- `reminders` cron: finds reminders where `{status: "pending", fires_at: {$lte: now}}`, writes one `inbox_messages` doc per fired reminder (with `type: "reminder"` and `metadata.reminder_id` linking back), then flips the reminder's `status` to `"fired"`.
- `weekly_summary` cron: runs `summarize_week` for the user, writes the result as one `inbox_messages` doc (`type: "weekly_summary"`, `metadata.week_start` set to the Monday string per the week-semantics contract in `architecture.md`).

The writers are crons, not agent tools — the agent doesn't write to this collection directly. (Future scope: a `read_inbox` agent tool so the agent can reference past summaries in conversation. Not in scope for the hackathon.)

## `langgraph_store` (managed)

LangGraph's MongoDB Store, GA in 2026. Namespaced agent memory (thread state, scratchpad, conversation history). We don't manage the schema — LangGraph does.

---

## Why one Atlas cluster

| Job                    | Where           | Why MongoDB                                       |
| ---------------------- | --------------- | ------------------------------------------------- |
| Operational records    | `transactions`, `goals`, `budgets`, `interventions`, `outcomes`, `user_context` | Schema-flexible, fast indexed reads |
| Semantic recall        | `memories.embedding` vector index                              | Atlas Vector Search built in        |
| Proactive inbox        | `inbox_messages` (written by the weekly_summary + reminders crons) | Same store, no second backend |
| Agent thread memory    | `langgraph_store`                                              | LangGraph adapter is first-class    |
| Query tuning           | MCP server                                                     | 40+ tools the agent can call itself |

One connection string. One backup story. One bill.
