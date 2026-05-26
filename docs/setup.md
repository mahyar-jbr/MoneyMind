# Setup

## Prereqs

- **Node 20+** and **pnpm 9+** (frontend)
- **Python 3.12+** and **uv** (backend, agent)
- **MongoDB Atlas account** — free tier (M0) works for dev
- **Google Cloud project** with the Vertex AI API enabled
- **Clerk account** (free dev tier)
- **Voyage AI key** (free tier covers dev)

## First-time setup (do this tonight — backlog item #1)

### 1. MongoDB Atlas

1. Create a free M0 cluster in the region closest to you (us-east-1 if unsure).
2. Add `0.0.0.0/0` to the IP allowlist for dev. **Tighten before submission.**
3. Create a database user with read+write on `moneymind`.
4. Copy the connection string → `.env` → `MONGODB_URI`.
5. Enable **Vector Search** on the cluster (Atlas UI → Search → Create Index).

### 2. Google Cloud

1. Create a new GCP project named `moneymind-hack`.
2. Enable the Vertex AI API.
3. Create a service account with `Vertex AI User`, download the JSON key.
4. Save it as `.gcloud/service-account.json` (gitignored).
5. Get a Gemini API key from AI Studio → `.env` → `GEMINI_API_KEY`.

### 3. Voyage AI

1. Sign up at voyageai.com, copy your API key → `.env` → `VOYAGE_API_KEY`.

### 4. Clerk

1. Create a new Clerk application (Next.js template).
2. Copy publishable + secret keys → `.env`.

### 5. Local install

```bash
# Frontend
cd frontend && pnpm i

# Backend
cd backend && uv sync

# Agent
cd agent && uv sync
```

## Daily run

```bash
# Three terminals (or use tmux / overmind)
cd frontend && pnpm dev                                            # :3000
cd backend  && uv run fastapi dev                                  # :8000
cd agent    && PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001  # :8001
```

`PYTHONPATH=..` on the agent line is required — `uv init --app` doesn't install the
project as a package, so without it uvicorn can't resolve `agent.serve`. See
`agent/README.md` for why and a follow-up ticket (#9a).

## Smoke test (after Sprint 1)

```bash
# 1. Load synthetic data
curl -X POST http://localhost:8000/ingest/csv \
  -F "file=@data/synthetic.csv"

# 2. Hit the agent
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u_482", "message": "How did I do this week?"}'
```

Expected: a paragraph that references actual numbers from the CSV.

## Common gotchas

- **Atlas vector index takes ~2 min to build.** First query after creation may 404.
- **Voyage auto-embed only fires on insert/update.** Existing docs need a separate backfill.
- **Clerk dev keys expire after 30 days.** Rotate before the demo.
- **Gemini rate limits on free tier.** Use exponential backoff in the agent; have stubbed responses ready as a video fallback.
