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

LangGraph orchestration on Gemini 3, deployed via Google Cloud Agent Builder.

- **Graph** — a small loop: `plan → call_tools → reflect → respond`. Reflection step decides whether to write a memory.
- **Tools (10)** — see [BACKLOG.md](../BACKLOG.md#sprint-2--the-agent-may-27--jun-2) for the full list. Each tool is a Python function with a JSON schema; LangGraph routes calls.
- **MCP client** — connects to the MongoDB MCP server for query tuning and schema introspection. The agent can call `explain()` on its own queries and self-optimize.
- **Cron** — once a week (8am Sunday user-local), a job kicks off the agent for each active user. Output lands in the user's in-app inbox.

## Layer 3 — Data + Memory (`/backend` + Atlas)

A single MongoDB Atlas instance doing four jobs.

| Job                | Collection(s)                                  | Notes                                                  |
| ------------------ | ---------------------------------------------- | ------------------------------------------------------ |
| Operational store  | `transactions`, `goals`, `interventions`, `outcomes`, `user_context` | Source of truth for app state                          |
| Vector store       | `memories.embedding` (auto-embed via Voyage)   | HNSW index, 1024 dim, semantic recall                  |
| Memory store       | `langgraph_store` (managed by LangGraph)       | GA, persistent, namespaced per user                    |
| Performance advisory | (via MCP server)                             | Agent uses 40+ MCP tools to inspect + tune queries     |

FastAPI sits in front: handles auth verification (Clerk JWT), CSV ingestion, aggregations, and proxies the agent's streaming output. It also runs the weekly cron.

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
6. **Outflow filters get a docstring.** Same as backend convention #3.
7. **Tools land "callable but unwired."** LangGraph binding happens in batches (#11a-style migrations), not per-tool. Tools must work when called directly with their input model — the demo proof in the ticket has to pass without the graph.
   - **Validate identifiers BEFORE any DB call.** Tools that take a string-form `ObjectId` (or any identifier parsed from input) must parse and validate it before reaching for the collection. On invalid input, raise `ValueError` with a clear message. Tests assert this via the **tripwire pattern**: monkeypatch the relevant collection method (e.g. `insert_one`, `find_one`) to record every call into a list, then assert the list is empty after the `ValueError` fires. Established by `#16` (goal_id), `#17` (related_memory_id), `#18` (intervention_id) — three uses, codified.
8. **External-service tools take an `embedder=None` (or service-specific) kwarg.** Any tool that calls a non-Mongo external service (Voyage, an LLM, an HTTP API) takes an injected callable kwarg in the same pattern as `collection=None`. Tests inject a fake. Established in `#13`'s `recall_memory(*, collection=None, embedder=None)`; mandatory for every subsequent tool that calls Voyage or any other external service.

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
