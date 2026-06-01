from fastapi.testclient import TestClient

from agent import serve


client = TestClient(serve.app)


def test_chat_streams_reply(monkeypatch):
    monkeypatch.setattr(
        serve,
        "stream_chat",
        lambda user_id, message: iter([f"echo:{user_id}:", message]),
    )

    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={"message": "How am I doing?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "echo:user_clerk_123:How am I doing?"


def test_chat_rejects_missing_internal_user_id(monkeypatch):
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 400


def test_chat_rejects_empty_message(monkeypatch):
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post(
        "/chat",
        headers={"X-MoneyMind-User-Id": "user_clerk_123"},
        json={"message": ""},
    )
    assert response.status_code == 400


def test_loopback_host_check_rejects_non_local_clients():
    assert serve._is_loopback_host("127.0.0.1") is True
    assert serve._is_loopback_host("::1") is True
    assert serve._is_loopback_host("203.0.113.10") is False
