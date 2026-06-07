from fastapi.testclient import TestClient

from agent import serve


client = TestClient(serve.app)


def _stub_astream(scripted_chunks):
    """Build an async-generator-returning callable to stub serve.astream_chat.
    Production path uses astream_chat (not stream_chat) since R-infra; the
    test must patch the same name."""

    async def _astream(user_id, message):  # noqa: ARG001
        for c in scripted_chunks(user_id, message):
            yield c

    return _astream


def test_chat_streams_reply_legacy_single_message(monkeypatch):
    """Legacy {message: str} wire still works (kept for curl scripts)."""
    monkeypatch.setattr(
        serve,
        "astream_chat",
        _stub_astream(lambda user_id, message: [f"echo:{user_id}:", message]),
    )

    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={"message": "How am I doing?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "echo:user_clerk_123:How am I doing?"


def test_chat_streams_reply_messages_history(monkeypatch):
    """Production {messages: [...]} wire forwards the full history shape
    into astream_chat so the agent can see prior turns."""
    received_messages: list = []

    def _capture(user_id, message):  # noqa: ARG001
        received_messages.append(message)
        return [f"echo:{user_id}:turns={len(message)}"]

    monkeypatch.setattr(serve, "astream_chat", _stub_astream(_capture))

    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={
            "messages": [
                {"role": "user", "content": "I'm bulking"},
                {"role": "assistant", "content": "Got it."},
                {"role": "user", "content": "what do you remember?"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.text == "echo:user_clerk_123:turns=3"
    # astream_chat received the message history as a list of role/content dicts.
    assert received_messages == [
        [
            {"role": "user", "content": "I'm bulking"},
            {"role": "assistant", "content": "Got it."},
            {"role": "user", "content": "what do you remember?"},
        ]
    ]


def test_chat_rejects_missing_internal_user_id(monkeypatch):
    monkeypatch.setattr(serve, "astream_chat", _stub_astream(lambda u, m: ["nope"]))
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 400


def test_chat_rejects_empty_message(monkeypatch):
    monkeypatch.setattr(serve, "astream_chat", _stub_astream(lambda u, m: ["nope"]))
    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={"message": ""},
    )
    assert response.status_code == 400


def test_chat_rejects_request_with_neither_field(monkeypatch):
    monkeypatch.setattr(serve, "astream_chat", _stub_astream(lambda u, m: ["nope"]))
    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={},
    )
    assert response.status_code == 400


def test_loopback_host_check_rejects_non_local_clients():
    assert serve._is_loopback_host("127.0.0.1") is True
    assert serve._is_loopback_host("::1") is True
    assert serve._is_loopback_host("203.0.113.10") is False


def test_agent_binds_loopback_only():
    assert serve.AGENT_HOST == "127.0.0.1"
