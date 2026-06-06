# Architecture

> Three layers. One agent. Clean separation between presentation, reasoning, and memory.

## Layer 1 — Presentation (`/frontend`)

Next.js 15 app on Vercel.

- **Streaming chat** — plain-text chunked stream from the agent through a thin FastAPI proxy (see § "Chat wire format" below; decided 2026-05-27, not SSE).
- **Dashboard** — weekly spend chart, goals, recent memories.
- **Intervention approval flow** — when the agent proposes a nudge, the UI surfaces an Accept / Decline / Modify card.
- **Auth** — Clerk. One user for the demo; the schema is namespaced per `user_id` so it generalizes.

Components: shadcn/ui + Tailwind. Animation: Framer Motion.

## Layer 2 — Reasoning (`/agent`)

LangGraph ReAct loop on **Gemini 2.5 Flash via Vertex AI** (`langchain-google-vertexai` / `ChatVertexAI`).

- **Graph** — `create_react_agent` over the native tools + MCP tools; `user_id` is carried in graph state via `InjectedState` so the LLM never sees or forges it. The agent decides for itself when to recall/write memory.
- **Tools (11)** — see [BACKLOG.md](../BACKLOG.md#sprint-2--the-agent-may-27--jun-2) for the full list. Each is a Python function with a Pydantic schema; LangGraph routes calls.
- **MCP client** — lazy-spawns the MongoDB MCP server as a stdio subprocess (`npx -y mongodb-mcp-server@latest --readOnly`) on the first chat turn and exposes its read tools as `mongo_*` for schema introspection and query tuning. Spawn failure degrades gracefully to the native tools.
- **Weekly summary + reminders** — exposed as `POST /agent/run-weekly-summary` and `POST /agent/run-reminders`; output lands in the user's in-app inbox. For the hackathon these are triggered externally (manual curl per take); an automated scheduler is deferred post-freeze.

## Layer 3 — Data + Memory (`/backend` + Atlas)

A single MongoDB Atlas instance doing four jobs.

| Job                | Collection(s)                                  | Notes                                                  |
| ------------------ | ---------------------------------------------- | ------------------------------------------------------ |
| Operational store  | `transactions`, `goals`, `interventions`, `outcomes`, `user_context` | Source of truth for app state                          |
| Vector store       | `memories.embedding` (Voyage, written on insert) | HNSW index, 1024 dim, semantic recall; not auto-embed |
| Memory store       | `langgraph_store` (managed by LangGraph)       | GA, persistent, namespaced per user                    |
| Performance advisory | (via MCP server)                             | Agent uses the read-only MongoDB MCP server's tools to inspect + tune queries |

FastAPI sits in front: handles auth verification (Clerk JWT), CSV ingestion, aggregations, and proxies the agent's streaming output. It also exposes the weekly-summary + reminder endpoints (`POST /agent/run-weekly-summary`, `POST /agent/run-reminders`) that the cron logic lives behind — those are currently triggered by authenticated manual POST (an automated scheduler is deferred post-freeze).

## Data flow (the slide-10 picture in words)

```
USER ──▶ frontend ──▶ /chat ──▶ agent ──▶ tools ──▶ Atlas
                                  │
                                  ▼
                              writes memory
                                  │
                                  ▼
                          outbound nudge ──▶ user inbox
```

1. **READ** — agent queries transactions + recalls memories + reads user context.
2. **REASON** — Gemini plans tool calls, executes them, reflects on the result.
3. **WRITE** — agent writes a new memory (if confidence > 0.5) and any intervention proposal back to Atlas; nudge streams back to the user.

## Backend route conventions

These apply to every FastAPI route. The reviewer Claude treats violations as blocking.

1. **`user_id` is always required, never defaulted.** Until Clerk JWT resolution lands (#4a), every route accepts `user_id` as a required query/form/path param. No `Query("u_482")` defaults — they leak data to the demo user the moment any route becomes public.
2. **Date ranges are inclusive on both ends.** If you accept `?to=2026-05-31`, transactions *on* May 31 must be included. Implement as `$lt next_day` or `$lte end_of_day`.
3. **Outflow vs. inflow filters get a docstring.** `amount: {$lt: 0}` is "spending only." Future contributors will confuse this without a comment.
4. **One resource per file in `app/api/`.** Group routes by domain (`transactions.py`, `aggregations.py`, `chat.py`), not by HTTP verb.

## Agent tool conventions

These apply to every tool under `agent/tools/`. The reviewer Claude treats violations as blocking. Decided 2026-05-27 (see `docs/decisions.md`).

1. **One tool per file.** `agent/tools/<tool_name>.py`. The file owns the input model, the output model(s), and the async callable. No multi-tool modules.
2. **Tools return Pydantic models, not dicts.** Input is a Pydantic model, output is a Pydantic model (or a Pydantic model wrapping a list of models). No `dict` in the return type.
3. **`collection=None` kwarg for dependency injection.** Every Mongo-touching tool takes `*, collection=None` and falls back to `agent.db.client.get_database().<coll>`. Tests pass a `mongomock-motor` fake to skip Atlas.
4. **`user_id` is required on the input model.** `Field(min_length=1)`. Same reason as backend route convention #1 — no defaults that silently leak to the demo user.
5. **Date semantics match backend convention #2.** Inclusive on both ends. Implement upper bound as `$lt next_day(date_to)`.
   - **Calendar-day fields persist as naive midnight datetimes.** Fields representing a calendar day the user thinks of in day-granular terms (`transactions.date`, `memories.evidence[].date`, `user_context.active_from`, `goals.target_date`, etc.). Naive datetime at 00:00 UTC. Established by `#11`.
   - **Instant-in-time fields persist as UTC instants.** Fields representing a moment in time the cron or another scheduler compares to "now" (`reminders.fires_at`, `reminders.fired_at`). UTC-aware in-process; pymongo strips tzinfo on store but the wall-clock value is preserved so comparisons still resolve. Deliberate exception to the calendar-day rule, established by `#19`. Naive datetime + cron across timezones is a category of production bug we don't invite.
6. **Outflow filters get a docstring.** Same as backend convention #3.
7. **Tools land "callable but unwired."** LangGraph binding happens in batches (#11a-style migrations), not per-tool. Tools must work when called directly with their input model — the demo proof in the ticket has to pass without the graph.
   - **Validate identifiers BEFORE any DB call.** Tools that take a string-form `ObjectId` (or any identifier parsed from input) must parse and validate it before reaching for the collection. On invalid input, raise `ValueError` with a clear message. Tests assert this via the **tripwire pattern**: monkeypatch the relevant collection method (e.g. `insert_one`, `find_one`) to record every call into a list, then assert the list is empty after the `ValueError` fires. Established by `#16` (goal_id), `#17` (related_memory_id), `#18` (intervention_id) — three uses, codified.
   - **Instrument production tools by patching the module-level callable, NOT by wrapping the `StructuredTool.coroutine`.** LangGraph's `InjectedState` routing inspects the wrapper function's signature for the `Annotated[dict, InjectedState]` parameter; a generic `*args, **kwargs` shim wrapped around `tool.coroutine` doesn't have that annotation, so state never gets injected and the inner runner crashes with `missing positional argument: 'state'`. The `_wrap_tool` closure captures the underlying production callable at `_build_tools()` call-time, so patching the module-level binding (e.g. `agent.graphs.main.summarize_week = recorder`) before `build_graph()` runs makes the wrapper pick up the recorder. This is the same pattern the existing `test_graph.py` tests use; `agent/scripts/demo_graph_full.py` (`#17-wire`) is the live-demo primitive for `#25p` voice tuning.
8. **External-service tools take an `embedder=None` (or service-specific) kwarg.** Any tool that calls a non-Mongo external service (Voyage, an LLM, an HTTP API) takes an injected callable kwarg in the same pattern as `collection=None`. Tests inject a fake. Established in `#13`'s `recall_memory(*, collection=None, embedder=None)`; mandatory for every subsequent tool that calls Voyage or any other external service.
   - **Same pattern applies to Mongo helpers that mongomock can't simulate.** When a tool delegates to an aggregation helper that uses operators mongomock-motor doesn't implement (e.g. `$dateTrunc`, `$vectorSearch`), inject the helper as a kwarg too — production defaults to the real helper, tests inject a scripted callable. Established in `#20`'s `summarize_week(*, collection=None, goals_collection=None, aggregator=None)`. Same hermeticity guarantee as Voyage injection; same convention, broader scope.

## Week semantics

Decided 2026-06-02 (see `docs/decisions.md`). The wire format for any week reference is a plain ISO date string `YYYY-MM-DD` denoting the Monday that starts the week. No time component, no zone suffix. Five implementations of "week" coexist in the codebase today:

- `agent/tools/summarize_week.py` — Python `weekday()` arithmetic on a `date`, Monday start. Canonical for the agent + cron output.
- `backend/app/cron/` (`weekly_summary.py`, `reminders.py`) — same Python `weekday()`.
- `backend/app/aggregations/weekly.py` — Mongo `$dateTrunc { unit: "week", startOfWeek: "monday" }` on the stored UTC-midnight `date` field.
- `agent/tools/get_spend_anomaly.py` — anchored 7-day buckets. Deliberately different (anomaly tool, not calendar). NOT a week formatter.
- `frontend/lib/dashboard.ts` — `formatWeek` / `formatDate`.

**The contract:**

- Week references on the wire are `YYYY-MM-DD` strings, no time, no zone.
- The string IS the Monday — UTC-midnight semantics. Anything storing a datetime must use UTC-midnight; anything parsing a string must interpret it as UTC, not local.
- All formatters that render a week label must parse the string as UTC (`new Date(d + "T00:00:00Z")` in TS; `datetime.combine(d, time(), UTC)` in Python) AND format with `timeZone: "UTC"`. `formatWeek` and `formatDate` in `frontend/lib/dashboard.ts` were patched in `#21a` to enforce this; before the patch they parsed as local time, which would show "May 17" instead of "May 18" for any user in a negative-UTC offset if the backend ever sent a datetime instead of a date string.

Post-freeze: extract a shared `week_bounds(d) -> (date, date)` helper across the four backend/agent call sites so a sixth definition can't sneak in. Tracked as `#21a-helper`.

## Chat wire format

Decided 2026-05-27 (see `docs/decisions.md`). All three legs use the same format:

```
agent /chat  ──▶  FastAPI /chat proxy  ──▶  Next.js /api/chat  ──▶  chat-stream.ts
```

- **Transport:** HTTP chunked response, `Content-Type: text/plain; charset=utf-8`. Not SSE.
- **Payload:** raw UTF-8 text tokens, streamed in order. No `data:` prefix, no event framing.
- **End of stream:** the connection closes. No sentinel token.
- **Errors mid-stream:** close the connection; the client surfaces a retry affordance and the user re-sends.

The proxy legs are transparent pass-throughs — they forward chunks as received, they don't buffer the full response. If we ever need structured events (tool-call traces, the cron nudge channel), that's a separate decision, not a change to this one.

## What's swappable

- Gemini → any LLM (LangGraph abstracts the call).
- Voyage → any embedder Atlas supports.
- Clerk → any JWT provider.
- Vercel/Railway → any hosting.

Atlas itself is **not** swappable — it's the spine. That's the point of the MongoDB-track pitch.
