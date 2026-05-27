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
        "/chat?user_id=u_482",
        json={"message": "How am I doing?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "echo:u_482:How am I doing?"


def test_chat_rejects_missing_user_id(monkeypatch):
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 400


def test_chat_rejects_empty_message(monkeypatch):
    monkeypatch.setattr(serve, "stream_chat", lambda user_id, message: iter(["nope"]))
    response = client.post("/chat?user_id=u_482", json={"message": ""})
    assert response.status_code == 400
