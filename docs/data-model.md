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
  source: "csv_import_2026-05-21",
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
  created_at: ISODate(...)
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
  embedding: [/* 1024 dims, auto-embedded by Voyage */],
  created_at: ISODate(...),
  last_used: ISODate(...),
  use_count: 3
}
```

**Vector index:** `memories.embedding` — HNSW, 1024 dim, cosine. Recalled via `recall_memory(query, k=5)`.

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
  user_response: "accepted",            // accepted | declined | modified | ignored
  responded_at: ISODate(...),
  related_memory: ObjectId              // optional FK to memories._id
}
```

## `outcomes`

Did the intervention work? Closes the learning loop.

```js
{
  _id: ObjectId,
  intervention_id: ObjectId,
  user_id: "u_482",
  measured_at: ISODate(...),
  window_days: 14,
  metric: "weekly_food_spend",
  before: 180.00,
  after: 118.50,
  delta_pct: -34.2,
  agent_judgment: "successful"          // successful | partial | failed | inconclusive
}
```

Agent reads recent outcomes when proposing similar interventions in the future.

## `langgraph_store` (managed)

LangGraph's MongoDB Store, GA in 2026. Namespaced agent memory (thread state, scratchpad, conversation history). We don't manage the schema — LangGraph does.

---

## Why one Atlas cluster

| Job                    | Where           | Why MongoDB                                       |
| ---------------------- | --------------- | ------------------------------------------------- |
| Operational records    | `transactions`, `goals`, `interventions`, `outcomes`, `user_context` | Schema-flexible, fast indexed reads |
| Semantic recall        | `memories.embedding` vector index                              | Atlas Vector Search built in        |
| Agent thread memory    | `langgraph_store`                                              | LangGraph adapter is first-class    |
| Query tuning           | MCP server                                                     | 40+ tools the agent can call itself |

One connection string. One backup story. One bill.
