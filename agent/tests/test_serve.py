from fastapi.testclient import TestClient

from agent import serve
from agent.auth.clerk import AuthenticatedUser


client = TestClient(serve.app)


def _override_user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id="user_clerk_123", token="jwt")


def test_chat_streams_reply(monkeypatch):
    serve.app.dependency_overrides[serve.current_user] = _override_user
    monkeypatch.setattr(
        serve,
        "stream_chat",
        lambda user_id, message: iter([f"echo:{user_id}:", message]),
    )

    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer jwt"},
        json={"message": "How am I doing?"},
    )

    serve.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "echo:user_clerk_123:How am I doing?"


def test_chat_rejects_missing_authorization(monkeypatch):
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_rejects_empty_message(monkeypatch):
    serve.app.dependency_overrides[serve.current_user] = _override_user
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post(
        "/chat",
        headers={"Authorization": "Bearer jwt"},
        json={"message": ""},
    )
    serve.app.dependency_overrides.clear()
    assert response.status_code == 400
