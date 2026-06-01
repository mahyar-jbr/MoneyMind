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
async def test_chat_proxy_forwards_authorization_to_agent(monkeypatch):
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
    assert _SEEN["headers"]["Authorization"] == "Bearer clerk.jwt"
    assert _SEEN["headers"]["X-MoneyMind-User-Id"] == "user_clerk_123"
    assert _SEEN["json"] == {"message": "How am I doing?"}
    assert _SEEN["raise_for_status_called"] is True
    assert _SEEN["closed"] is True
