# agent — LangGraph + Gemini

**Owner:** @mahyar
**Stack:** Python 3.12 · uv · LangGraph · Gemini 2.5 Flash on Vertex AI (langchain-google-vertexai) · Motor · Voyage AI

## First-time setup

Run **inside this folder**:

The canonical dependency set lives in `agent/pyproject.toml` / `uv.lock` — to build
the env, just `uv sync` inside `agent/`. The original scaffold (kept for history):

```bash
# 1. Init uv project
uv init --app .

# 2. Add the libs (LLM layer is Vertex AI, NOT the AI-Studio google-genai SDK)
uv add langgraph langchain-google-vertexai langchain-mcp-adapters motor pymongo voyageai \
       python-dotenv pydantic pydantic-settings httpx
uv add --dev pytest pytest-asyncio ruff

# 3. Create the entrypoint (Mahyar will do this in ticket #9)
#    agent/serve.py with: a minimal FastAPI app exposing POST /chat

# 4. Run (from inside agent/)
PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001
```

`PYTHONPATH=..` puts the repo root on `sys.path` so `agent.serve` resolves —
`uv init --app` does not install the project as a package, so without it
uvicorn can't find the `agent` module. Don't "fix" this by dropping the
`agent.` prefix; the package layout is intentional.

The agent runs on port 8001. It's called by the backend (which proxies user chat to it).

## Folder conventions

| Folder         | What goes here                                                  |
| -------------- | --------------------------------------------------------------- |
| `serve.py`     | FastAPI entrypoint exposing `/chat` (SSE stream)                |
| `graphs/`      | LangGraph definitions. `main.py` is the primary graph.          |
| `tools/`       | Individual tools (one file per tool, named `query_transactions.py` etc.) |
| `memory/`      | Vector store wrapper, LangGraph store config, embedding helpers |
| `prompts/`     | System prompts, tool descriptions, persona definitions          |
| `tests/`       | pytest tests for tools and graph nodes                          |

## Env vars (read from repo-root `.env`)

```python
# serve.py
from dotenv import load_dotenv
load_dotenv("../.env")
```

Variables this service uses:
- `MONGODB_URI`
- `MONGODB_DB`
- `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` (Vertex AI ADC, R2). In the container, `deploy/entrypoint.sh` derives `GOOGLE_APPLICATION_CREDENTIALS` from `GOOGLE_APPLICATION_CREDENTIALS_JSON_B64`.
- `VOYAGE_API_KEY`
- `MONGODB_MCP_DISABLE=1` (optional kill switch) / `MONGODB_MCP_TRANSPORT` (default `stdio`) — the MCP server is a stdio subprocess; there is no `MCP_ENABLED`/`MCP_SERVER_URL`.

## What ships in Sprint 1

- BACKLOG #9 — Minimum LangGraph loop (1 node, Gemini call, returns a paragraph)
- BACKLOG #10 — Glue: end-to-end CSV → agent paragraph (joint with @kasra, @aidin)

## What ships in Sprint 2

- BACKLOG #11–20 — 10 agent tools (one per file in `tools/`)
- BACKLOG #24 — Wire MongoDB MCP server

## Conventions

- **One tool per file.** Easier to test, easier to swap, easier to skim during code review.
- **Tools return Pydantic models, not dicts.** LangGraph + Gemini both work better with typed responses.
- **Prompts live in `prompts/`, not inline.** Keeps the graph code readable and lets us iterate on tone without touching logic.
- **No business logic in `serve.py`.** It's a thin HTTP layer. All reasoning lives in `graphs/`.

## Agent persona (from the pitch)

Warm. Concrete. References specific dollar amounts and past dates. Never preachy. Never says "I'm an AI" or "as a language model." Tone: a sharp friend who remembers your last conversation.
