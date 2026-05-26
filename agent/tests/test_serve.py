from fastapi.testclient import TestClient

from agent import serve
from agent.graphs.main import MODEL_NAME


client = TestClient(serve.app)


def test_chat_returns_reply(monkeypatch):
    monkeypatch.setattr(serve, "run_chat", lambda message: f"echo: {message}")

    response = client.post(
        "/chat",
        json={"user_id": "u_482", "message": "How am I doing?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "user_id": "u_482",
        "reply": "echo: How am I doing?",
        "model": MODEL_NAME,
    }


def test_chat_rejects_missing_user_id():
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 400


def test_chat_rejects_empty_message(monkeypatch):
    monkeypatch.setattr(serve, "run_chat", lambda message: "should not be called")
    response = client.post("/chat", json={"user_id": "u_482", "message": ""})
    assert response.status_code == 400


def test_chat_returns_500_on_agent_failure(monkeypatch):
    def boom(_message: str) -> str:
        raise RuntimeError("gemini exploded")

    monkeypatch.setattr(serve, "run_chat", boom)

    response = client.post(
        "/chat",
        json={"user_id": "u_482", "message": "hi"},
    )
    assert response.status_code == 500
