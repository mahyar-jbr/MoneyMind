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
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.graphs.main import MODEL_NAME, run_chat


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

app = FastAPI(title="MoneyMind Agent", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def _validation_to_400(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    user_id: str
    reply: str
    model: str


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        reply = run_chat(payload.message)
    except Exception:
        logger.exception("agent run failed")
        raise HTTPException(status_code=500, detail="agent failed")
    return ChatResponse(user_id=payload.user_id, reply=reply, model=MODEL_NAME)


def main() -> None:
    import uvicorn

    uvicorn.run("agent.serve:app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
    main()
