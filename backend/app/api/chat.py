import os

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.clerk import AuthenticatedUser, current_user


router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    """Accepts either {messages: [...]} (production wire) or {message: str}
    (legacy single-turn wire). Always forwards in whichever shape it
    received, so the agent can reconstruct the conversation thread."""

    message: str | None = None
    messages: list[ChatMessage] | None = None


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> StreamingResponse:
    """Transparent streaming proxy from the frontend to the agent.

    Forwards the user's message(s) to the agent's /chat and pipes the
    agent's plain-text token stream straight back to the caller, chunk
    by chunk, with no buffering. Wire format: text/plain chunked (see
    docs/architecture.md § "Chat wire format"). Conversation history is
    forwarded as `messages` so multi-turn features (V3 forget_memory
    confirmation, slide-8 chain) see prior tool calls + replies.
    """
    agent_url = os.getenv("AGENT_URL", "http://localhost:8001")

    if payload.messages is not None:
        agent_body: dict = {"messages": [m.model_dump() for m in payload.messages]}
    elif payload.message is not None:
        agent_body = {"message": payload.message}
    else:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="chat request requires `messages` or `message`"
        )

    async def upstream():
        client = httpx.AsyncClient(timeout=None)
        try:
            async with client.stream(
                "POST",
                f"{agent_url}/chat",
                headers={"X-MoneyMind-User-Id": user.user_id},
                json=agent_body,
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
