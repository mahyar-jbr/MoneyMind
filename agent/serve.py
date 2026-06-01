"""MoneyMind agent service.

Run from inside the `agent/` directory:

    uv sync
    PYTHONPATH=.. uv run uvicorn agent.serve:app --port 8001

PYTHONPATH=.. is required because `uv init --app` does not install the
project, so `agent` is not on sys.path by default — adding the repo root
makes `agent.serve` importable.
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent.auth.clerk import AuthenticatedUser, current_user
from agent.graphs.main import stream_chat


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

app = FastAPI(title="MoneyMind Agent", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat")
def chat(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> StreamingResponse:
    """Stream the agent's reply as plain-text chunks.

    Wire format: text/plain chunked, no SSE (see docs/architecture.md
    § "Chat wire format"). The connection closing is the end of stream.
    """

    def tokens():
        try:
            for chunk in stream_chat(user.user_id, payload.message):
                yield chunk
        except Exception:
            logger.exception("agent run failed")
            # Stream is already open; closing the connection signals the error
            # to the client per the wire-format contract (client re-sends).
            return

    return StreamingResponse(
        tokens(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def main() -> None:
    import uvicorn

    uvicorn.run("agent.serve:app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
    main()
