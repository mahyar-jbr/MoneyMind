"""MoneyMind agent service.

Run from inside the `agent/` directory:

    uv sync
    PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001

PYTHONPATH=.. is required because `uv init --app` does not install the
project, so `agent` is not on sys.path by default — adding the repo root
makes `agent.serve` importable.
"""

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


# The agent graph pulls langchain_google_vertexai + langgraph + 11 tool
# modules — cold import is 60-240s on a fresh interpreter. We keep this
# out of the module-load path (so /health and uvicorn's "ready" announce
# are instant) and warm it in a background thread during the lifespan
# startup hook. `/chat` requests block on `_warmed.wait()` until the
# import finishes — on a warm container that's nanoseconds.
#
# Tests monkeypatch `serve.stream_chat` directly to bypass the warmup.

# Sync stream_chat is kept for tests that monkeypatch it. Production uses
# astream_chat — see chat() below.
stream_chat = None  # type: ignore[assignment]
astream_chat = None  # type: ignore[assignment]
_warmed = threading.Event()


def _load_chat_callables() -> None:
    """Import agent.graphs.main.{stream_chat,astream_chat} and cache both."""
    global stream_chat, astream_chat
    if astream_chat is not None:
        return
    from agent.graphs.main import astream_chat as _astream_chat
    from agent.graphs.main import stream_chat as _stream_chat
    stream_chat = _stream_chat  # type: ignore[assignment]
    astream_chat = _astream_chat  # type: ignore[assignment]


def _warm_in_background() -> None:
    """Run on a thread during lifespan startup; populates both callables."""
    try:
        _load_chat_callables()
    except Exception:  # noqa: BLE001 — log and continue; /chat will retry
        logging.getLogger(__name__).exception("graph warm-up failed")
    finally:
        _warmed.set()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Kick the heavy graph import onto a thread at startup so uvicorn
    can announce 'ready' immediately. /chat blocks on _warmed."""
    threading.Thread(target=_warm_in_background, name="graph-warm", daemon=True).start()
    yield


logger = logging.getLogger(__name__)
AGENT_HOST = "127.0.0.1"

app = FastAPI(title="MoneyMind Agent", version="0.1.0", lifespan=_lifespan)


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """Two-shape request body for backwards compatibility:
      - {"messages": [{"role": "user"|"assistant", "content": str}, ...]}
        is the production shape — carries the full conversation thread so
        multi-turn features (V3 forget_memory confirmation, slide-8 chain)
        can see prior tool calls + replies.
      - {"message": str} is the legacy single-turn shape; kept so existing
        tests + curl smoke scripts don't break. Treated as a one-message
        history with role="user".
    """

    message: str | None = Field(default=None, min_length=1)
    messages: list[ChatMessage] | None = Field(default=None, min_length=1)

    def to_history(self) -> str | list[dict]:
        if self.messages is not None:
            return [{"role": m.role, "content": m.content} for m in self.messages]
        if self.message is not None:
            return self.message
        raise ValueError("ChatRequest requires either `messages` or `message`")


def _require_loopback_client(request: Request) -> None:
    host = request.client.host if request.client else None
    if not _is_loopback_host(host):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="agent /chat only accepts loopback backend calls",
        )


def _is_loopback_host(host: str | None) -> bool:
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    user_id: str = Header(..., alias="X-MoneyMind-User-Id", min_length=1),
) -> StreamingResponse:
    """Stream the agent's reply as plain-text chunks.

    Wire format: text/plain chunked, no SSE (see docs/architecture.md
    § "Chat wire format"). The connection closing is the end of stream.
    """
    _require_loopback_client(request)
    if astream_chat is None:
        # Warmup not finished yet. Wait off the event loop so we don't
        # starve other requests. 240s upper bound mirrors Vertex's cold
        # import worst case observed locally.
        await asyncio.get_event_loop().run_in_executor(
            None, _warmed.wait, 240
        )
        if astream_chat is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="agent warming up; retry in a few seconds",
            )

    try:
        history = payload.to_history()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def tokens():
        try:
            async for chunk in astream_chat(user_id, history):
                yield chunk
        except Exception:
            logger.exception("agent run failed")
            # Stream is already open; closing the connection signals the
            # error to the client per the wire-format contract.
            return

    return StreamingResponse(
        tokens(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def main() -> None:
    import uvicorn

    uvicorn.run("agent.serve:app", host=AGENT_HOST, port=8001, reload=False)


if __name__ == "__main__":
    main()
