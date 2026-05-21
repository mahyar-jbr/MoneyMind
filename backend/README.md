# backend — FastAPI service

**Owner:** @kasra
**Stack:** FastAPI · Python 3.12 · uv (package mgr) · Motor (async MongoDB)

## First-time setup

Run **inside this folder**:

```bash
# 1. Init uv project (creates pyproject.toml, .python-version)
uv init --app .

# 2. Add the libs we'll use
uv add fastapi "uvicorn[standard]" motor pymongo python-dotenv pydantic pydantic-settings
uv add --dev pytest pytest-asyncio httpx ruff

# 3. Create the app entrypoint (Kasra will do this in ticket #4)
#    app/main.py with: from fastapi import FastAPI; app = FastAPI()

# 4. Run
uv run uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs — auto-generated OpenAPI docs.

## Folder conventions

| Folder              | What goes here                                              |
| ------------------- | ----------------------------------------------------------- |
| `app/main.py`       | FastAPI app entrypoint, route registration                  |
| `app/api/`          | Route handlers, grouped by resource (`transactions.py`, etc.) |
| `app/ingestion/`    | CSV parser, bulk insert logic                               |
| `app/aggregations/` | MongoDB aggregation pipelines (weekly spend, anomalies)     |
| `app/db/`           | Motor client setup, connection pooling                      |
| `app/cron/`         | Scheduled jobs (weekly agent trigger)                       |
| `tests/`            | pytest tests, mirror the `app/` structure                   |

## Env vars (read from repo-root `.env`)

Use `python-dotenv` to load from `../.env`:

```python
# app/main.py
from dotenv import load_dotenv
load_dotenv("../.env")
```

Variables this service uses:
- `MONGODB_URI`
- `MONGODB_DB`
- `CLERK_SECRET_KEY` (for JWT verification on protected routes)
- `AGENT_URL` (defaults to http://localhost:8001)

## What ships in Sprint 1

- BACKLOG #4 — `POST /ingest/csv` → transactions collection
- BACKLOG #5 — `GET /agg/weekly` → spend by category
- BACKLOG #6 — Synthetic dataset generator (writes to `../data/synthetic.csv`)

## API contracts (Kasra: agree these with Aidin in standup)

```
POST /ingest/csv         multipart upload → { inserted: int, errors: [] }
GET  /agg/weekly         ?user_id&from&to → { weeks: [{ week, by_category }] }
POST /chat               { user_id, message } → SSE stream of agent tokens
                         (this one proxies to the agent service)
```

Lock these shapes early. Changing them mid-sprint breaks the frontend.
