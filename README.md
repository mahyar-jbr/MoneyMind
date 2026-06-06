# MoneyMind

**An AI co-pilot that remembers who you are with money.**

> Google Cloud Rapid Agent Hackathon · MongoDB Track
> Code freeze: **June 4, 2026** · Submission: **June 11, 2026**
> Live: **[money-mind-seven.vercel.app](https://money-mind-seven.vercel.app)**

---

## What it is

A personal finance agent that learns your patterns, holds the context you give it ("I'm bulking this month", "birthday party this week"), and acts proactively — instead of waiting for you to open an app and stare at a pie chart.

## Why it's different

Every finance app (Mint, YNAB, Cleo, Copilot, Monarch) has a memory of your **transactions**. MoneyMind has a memory of **you** — your patterns, your stated context, your goals, and how you've responded to past nudges.

A real exchange from the live app:

> **You:** how was my spending this week
> **MoneyMind:** You've spent about \$214 this week, mainly on Food Delivery (\$168) and Amazon (\$29). That's heavily weighted towards food delivery – anything going on?
>
> **You:** oo shit, sorry man this week im having a birthday party so im gonna spend little bit more to buy a gift
> **MoneyMind:** No worries at all! Thanks for letting me know about the birthday party and gift this week. I'll keep that in mind as I track your spending.
>
> **You:** any advice for me this week
> **MoneyMind:** You've spent \$214 so far this week, with the biggest chunks going to Food Delivery (\$168) and Shopping Amazon (\$29). **Given the birthday party you're having, it makes sense you might be spending a bit more; is the Amazon purchase your gift?**

The agent remembered the birthday party from the previous turn and reasoned about the spend in that context. That's the entire product thesis on three messages.

## Stack

- **Frontend** — Next.js 15 · Tailwind · shadcn/ui · Framer Motion · Vercel
- **Backend** — FastAPI · Python · Railway (single Docker container, supervisord splits backend on `:8000` and agent on loopback `:8001`)
- **Agent** — Gemini 2.5 Flash on Vertex AI · LangGraph ReAct loop · 11 native tools + MongoDB MCP read tools
- **Data + Memory** — MongoDB Atlas · Voyage AI embeddings (vector search on `memories.embedding`, 1024-dim cosine) · MongoDB MCP Server
- **Auth** — Clerk (frontend → backend Bearer JWT, backend → agent `X-MoneyMind-User-Id` loopback)

## Architecture, in one diagram

```
browser ─Clerk JWT→ Vercel /api/chat ─stream→ FastAPI /chat ─loopback→ Agent /chat
                                                                            │
                                          (Lifespan warmup loads graph)     │
                                                                            ▼
                                                            LangGraph ReAct loop
                                                                ├─ summarize_week
                                                                ├─ get_spend_anomaly
                                                                ├─ query_transactions
                                                                ├─ recall_memory  ──┐
                                                                ├─ write_memory ────┤
                                                                ├─ update_user_context
                                                                ├─ check_goal_pace
                                                                ├─ propose_intervention
                                                                ├─ respond_to_intervention
                                                                ├─ log_outcome
                                                                ├─ schedule_reminder
                                                                ├─ mongo_aggregate   ── (R1 MCP)
                                                                └─ mongo_find        ── (R1 MCP)
                                                                          │
                                                                          ▼
                                                                  Atlas + Voyage
```

Every request stays on a single asyncio event loop end-to-end — `astream_chat` yields directly from `compiled.astream(...)`, so motor cursors (active-context fetch, memory recall) never cross loop boundaries. The agent boot is async-clean.

## MongoDB MCP integration (hackathon-track eligibility)

MoneyMind integrates the [MongoDB MCP Server](https://www.mongodb.com/docs/mcp-server/) via [`langchain-mcp-adapters`](https://pypi.org/project/langchain-mcp-adapters/), exposing Atlas read tools (`collection-schema`, `aggregate`, `find`, query plan inspection, etc.) to the agent as first-class LangGraph tools alongside the 11 native MoneyMind tools. The MCP subprocess is started with `--readOnly`, so the agent can explore the schema and tune its own queries but cannot mutate the database — a judge typing "drop the transactions collection" is structurally unable to do it. The Node 20 runtime that hosts the MCP subprocess is pre-staged in the Railway container alongside the Python agent, so the integration is a single-container deploy. See [`agent/mcp_integration/client.py`](agent/mcp_integration/client.py) for the lazy-spawn singleton and `agent/scripts/demo_mcp.py` for the live verification script. A `MONGODB_MCP_DISABLE=1` env-var kill switch is wired in case the upstream package regresses mid-demo.

## What works on the live URL right now

- **Sign in with Clerk → dashboard renders real spend** ($17,380 over 26 weeks, seeded synthetic data for user `u_482`)
- **Streaming chat** through Vercel → FastAPI → agent (text/plain chunked, no SSE, ~3–8s warm latency, 20–45s on a cold container)
- **All 11 native tools** wired into the ReAct loop with `InjectedState` so the LLM never sees or forges `user_id`
- **Active-context recall across turns** — say "I'm bulking" once, every future spend question reads that context
- **Recall→observe→consolidate memory loop** — first observation writes a low-confidence `reaction`; second matching event writes a higher-confidence `pattern` that supersedes it in vector recall
- **Intervention card render** — `propose_intervention` writes a PENDING doc, frontend polls, slide-8 card drops into the chat thread
- **MCP read tools** join the toolset as `mongo_*` whenever the MCP server can spawn cleanly; graceful fallback to the 11 native tools otherwise

## Quickstart (local)

```bash
git clone <repo>
cd moneymind
cp .env.example .env       # fill in keys, see docs/setup.md

# Frontend (port 3000)
cd frontend && pnpm i && pnpm dev

# Backend (port 8000)
cd backend && uv sync && uv run fastapi dev

# Agent (port 8001) — uvicorn announces ready in <1s; the heavy graph
# import (langchain_google_vertexai + langgraph + 11 tools) warms on a
# background thread during the FastAPI lifespan hook.
cd agent && uv sync && uv run python -m agent.serve
```

See [`BACKLOG.md`](./BACKLOG.md) for the sprint plan and [`docs/`](./docs/) for architecture, data model, and demo script.

## Demo

- Live: **[money-mind-seven.vercel.app](https://money-mind-seven.vercel.app)** — sign in, ask "how was my spending this week", give it context, ask again
- Video: _coming Jun 9_ — target 2:00–2:30
- Devpost: _coming Jun 11_

## Team

- **Mahyar** — Agent + memory architecture
- **Kasra** — Backend + data pipeline (4th yr, TMU Comp Sci)
- **Aidin** — Frontend + demo polish (Seneca grad)
