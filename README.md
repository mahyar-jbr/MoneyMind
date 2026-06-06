# MoneyMind

**An AI co-pilot that remembers who you are with money.**

> Google Cloud Rapid Agent Hackathon · MongoDB Track
> Code freeze: **June 4, 2026** · Submission: **June 11, 2026**

---

## What it is

A personal finance agent that learns your patterns, holds the context you give it ("I'm bulking this month"), and acts proactively — instead of waiting for you to open an app and stare at a pie chart.

## Why it's different

Every finance app (Mint, YNAB, Cleo, Copilot, Monarch) has a memory of your **transactions**. MoneyMind has a memory of **you** — your patterns, your stated context, your goals, and how you've responded to past nudges.

## Stack

- **Frontend** — Next.js 15 · Tailwind · shadcn/ui · Framer Motion · Vercel
- **Backend** — FastAPI · Python · Railway
- **Agent** — Gemini 3 · Google Cloud Agent Builder · LangGraph
- **Data + Memory** — MongoDB Atlas · Voyage AI auto-embed · MongoDB MCP Server
- **Auth** — Clerk

## MongoDB MCP integration (hackathon-track eligibility)

MoneyMind integrates the [MongoDB MCP Server](https://www.mongodb.com/docs/mcp-server/) via [`langchain-mcp-adapters`](https://pypi.org/project/langchain-mcp-adapters/), exposing Atlas read tools (`collection-schema`, `aggregate`, `find`, query plan inspection, etc.) to the agent as first-class LangGraph tools alongside the 11 native MoneyMind tools. The MCP subprocess is started with `--readOnly`, so the agent can explore the schema and tune its own queries but cannot mutate the database — a judge typing "drop the transactions collection" is structurally unable to do it. The Node 20 runtime that hosts the MCP subprocess is pre-staged in the Railway container alongside the Python agent, so the integration is a single-container deploy. See [`agent/mcp_integration/client.py`](agent/mcp_integration/client.py) for the lazy-spawn singleton and `agent/scripts/demo_mcp.py` for the live verification script.

## Quickstart

```bash
git clone <repo>
cd moneymind
cp .env.example .env       # fill in keys, see docs/setup.md

# Frontend (port 3000)
cd frontend && pnpm i && pnpm dev

# Backend (port 8000)
cd backend && uv sync && uv run fastapi dev

# Agent (port 8001)
cd agent && uv sync && uv run python -m agent.serve
```

See [`BACKLOG.md`](./BACKLOG.md) for the sprint plan and [`docs/`](./docs/) for architecture, data model, and demo script.

## Demo

- Live: _coming Jun 4_
- Video: _coming Jun 9_
- Devpost: _coming Jun 11_

## Team

- **Mahyar** — Agent + memory architecture
- **Kasra** — Backend + data pipeline (4th yr, TMU Comp Sci)
- **Aidin** — Frontend + demo polish (Seneca grad)
