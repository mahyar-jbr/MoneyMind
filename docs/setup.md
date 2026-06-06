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

### 2. Google Cloud (Vertex AI)

The agent calls **`gemini-2.5-flash` through Vertex AI** (`langchain-google-vertexai` /
`ChatVertexAI`), authenticated with Application Default Credentials from a service
account. It does **not** use an AI-Studio `GEMINI_API_KEY` — there is no such variable.

1. Create a GCP project (e.g. `moneymind-hack`) and note its ID.
2. Enable the **Vertex AI API** on the project.
3. Create a service account, grant it **`roles/aiplatform.user`**, and download the JSON key.
4. Save the key as `.gcloud/service-account.json` (gitignored).
5. Set in `.env`:
   - `GOOGLE_CLOUD_PROJECT=<your-project-id>`
   - `GOOGLE_CLOUD_LOCATION=us-central1`
   - `GOOGLE_APPLICATION_CREDENTIALS=./.gcloud/service-account.json`

> **Deploying to a container (Railway)?** Don't ship the JSON file — it's dockerignored.
> Instead set `GOOGLE_APPLICATION_CREDENTIALS_JSON_B64` to `base64 -i .gcloud/service-account.json | tr -d '\n'`;
> `deploy/entrypoint.sh` decodes it at boot. See `.env.example` for the full note.

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
cd backend  && uv run uvicorn app.main:app --reload --port 8000    # :8000
cd agent    && PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001  # :8001
```

`PYTHONPATH=..` on the agent line is required — `uv init --app` doesn't install the
project as a package, so without it uvicorn can't resolve `agent.serve`. See
`agent/README.md` for why and a follow-up ticket (#9a).

## Smoke test

Every backend route is Clerk-authenticated, so the curls need a bearer token. Put a
dev session token in `.env` as `CLERK_JWT` (grab it from `await getToken()` on a
signed-in page, or the Clerk session cookie in devtools), then:

```bash
# 1. Load synthetic data (Clerk-authed; the user is derived from the token)
curl -X POST http://localhost:8000/ingest/csv \
  -H "Authorization: Bearer $CLERK_JWT" \
  -F "file=@data/synthetic.csv"

# 2. Ask the agent — go through the backend /chat, not the agent directly.
#    The backend derives your user_id from the JWT and proxies to the agent over
#    loopback; the agent's own /chat only accepts in-container loopback callers,
#    so hitting :8001 from your shell is refused by design.
curl -N -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $CLERK_JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "How did I do this week?"}'
```

Expected: a streamed paragraph that references actual numbers from the CSV.

## Common gotchas

- **Atlas vector index takes ~2 min to build.** First query after creation may 404.
- **Embeddings are written explicitly on insert** (the agent embeds via Voyage before writing `memories.embedding`); Atlas auto-embed is not enabled. Hand-inserted memory docs without an `embedding` won't be recallable until re-written.
- **Clerk dev keys expire after 30 days.** Rotate before the demo.
- **Vertex auth is ADC, not an API key.** "`GOOGLE_CLOUD_PROJECT is not set`" or an ADC error on the first `/chat` means the service-account env vars (or `GOOGLE_APPLICATION_CREDENTIALS_JSON_B64` in prod) aren't set — see §2.
