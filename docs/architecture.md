# Architecture

> Three layers. One agent. Clean separation between presentation, reasoning, and memory.

## Layer 1 — Presentation (`/frontend`)

Next.js 15 app on Vercel.

- **Streaming chat** — server-sent events from the agent through a thin FastAPI proxy.
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

## What's swappable

- Gemini → any LLM (LangGraph abstracts the call).
- Voyage → any embedder Atlas supports.
- Clerk → any JWT provider.
- Vercel/Railway → any hosting.

Atlas itself is **not** swappable — it's the spine. That's the point of the MongoDB-track pitch.
