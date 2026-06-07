import pytest

from app.api import chat as chat_api
from app.auth.clerk import AuthenticatedUser


class _FakeStreamResponse:
    def __init__(self, seen: dict):
        self.seen = seen

    def raise_for_status(self) -> None:
        self.seen["raise_for_status_called"] = True

    async def aiter_bytes(self):
        yield b"agent reply"


class _FakeStreamContext:
    def __init__(self, seen: dict):
        self.seen = seen

    async def __aenter__(self):
        return _FakeStreamResponse(self.seen)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncClient:
    def __init__(self, *, timeout):
        self.timeout = timeout

    def stream(self, method, url, *, headers, json):
        _SEEN.update(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": self.timeout,
            }
        )
        return _FakeStreamContext(_SEEN)

    async def aclose(self):
        _SEEN["closed"] = True


_SEEN: dict = {}


@pytest.mark.asyncio
async def test_chat_proxy_forwards_legacy_single_message(monkeypatch):
    """Legacy {message: str} wire still passes through to the agent
    intact (kept for curl smoke scripts and pre-V3 callers)."""
    _SEEN.clear()
    monkeypatch.setenv("AGENT_URL", "http://agent.test")
    monkeypatch.setattr(chat_api.httpx, "AsyncClient", _FakeAsyncClient)

    response = await chat_api.chat(
        chat_api.ChatRequest(message="How am I doing?"),
        AuthenticatedUser(user_id="user_clerk_123", token="clerk.jwt"),
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert body == b"agent reply"
    assert _SEEN["method"] == "POST"
    assert _SEEN["url"] == "http://agent.test/chat"
    assert "Authorization" not in _SEEN["headers"]
    assert _SEEN["headers"]["X-MoneyMind-User-Id"] == "user_clerk_123"
    assert _SEEN["json"] == {"message": "How am I doing?"}
    assert _SEEN["raise_for_status_called"] is True
    assert _SEEN["closed"] is True


@pytest.mark.asyncio
async def test_chat_proxy_forwards_full_messages_history(monkeypatch):
    """Production wire: {messages: [...]} carries the full conversation
    so multi-turn features (V3 forget_memory confirmation, slide-8 chain)
    have prior tool calls + replies in scope. The pre-V3 wire dropped all
    but the last user message and broke confirmation flows."""
    _SEEN.clear()
    monkeypatch.setenv("AGENT_URL", "http://agent.test")
    monkeypatch.setattr(chat_api.httpx, "AsyncClient", _FakeAsyncClient)

    request = chat_api.ChatRequest(
        messages=[
            chat_api.ChatMessage(role="user", content="I'm bulking"),
            chat_api.ChatMessage(role="assistant", content="Got it."),
            chat_api.ChatMessage(role="user", content="what do you remember?"),
        ]
    )
    response = await chat_api.chat(
        request,
        AuthenticatedUser(user_id="user_clerk_123", token="clerk.jwt"),
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert body == b"agent reply"
    # Headers identical to the legacy path.
    assert _SEEN["headers"]["X-MoneyMind-User-Id"] == "user_clerk_123"
    # Body forwards the messages array as-is, NOT downgraded to a single
    # `message` field.
    assert _SEEN["json"] == {
        "messages": [
            {"role": "user", "content": "I'm bulking"},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "what do you remember?"},
        ]
    }
