import os

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.clerk import AuthenticatedUser, current_user


router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> StreamingResponse:
    """Transparent streaming proxy from the frontend to the agent.

    Forwards the user's message to the agent's /chat and pipes the agent's
    plain-text token stream straight back to the caller, chunk by chunk, with
    no buffering. Wire format: text/plain chunked (see docs/architecture.md
    § "Chat wire format").
    """
    agent_url = os.getenv("AGENT_URL", "http://localhost:8001")

    async def upstream():
        client = httpx.AsyncClient(timeout=None)
        try:
            async with client.stream(
                "POST",
                f"{agent_url}/chat",
                headers={"X-MoneyMind-User-Id": user.user_id},
                json={"message": payload.message},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
        finally:
            await client.aclose()

    return StreamingResponse(
        upstream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
