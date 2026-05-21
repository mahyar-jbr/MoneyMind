# agent — LangGraph + Gemini

**Owner:** @mahyar
**Stack:** Python 3.12 · uv · LangGraph · Gemini 3 (via google-genai) · Motor · Voyage AI

## First-time setup

Run **inside this folder**:

```bash
# 1. Init uv project
uv init --app .

# 2. Add the libs
uv add langgraph langchain-google-genai google-genai motor pymongo voyageai \
       python-dotenv pydantic pydantic-settings httpx
uv add --dev pytest pytest-asyncio ruff

# 3. Create the entrypoint (Mahyar will do this in ticket #9)
#    agent/serve.py with: a minimal FastAPI app exposing POST /chat

# 4. Run
uv run python -m agent.serve
```

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
- `GEMINI_API_KEY`
- `VOYAGE_API_KEY`
- `MCP_ENABLED`, `MCP_SERVER_URL` (Sprint 2)

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
