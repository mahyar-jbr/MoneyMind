from fastapi import HTTPException
import pytest

from agent.auth import clerk


class _FakeSigningKey:
    key = "public-key"


class _FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        assert token == "jwt"
        return _FakeSigningKey()


def test_current_user_requires_bearer_header():
    with pytest.raises(HTTPException) as exc:
        clerk.current_user(None)

    assert exc.value.status_code == 401


def test_verify_clerk_token_returns_subject(monkeypatch):
    issuer = "https://demo.clerk.accounts.dev"
    calls = []

    def fake_decode(token, key=None, algorithms=None, issuer=None, options=None):
        calls.append((token, key, algorithms, issuer, options))
        if options == {"verify_signature": False}:
            return {"iss": "https://demo.clerk.accounts.dev"}
        assert key == "public-key"
        assert algorithms == ["RS256"]
        assert issuer == "https://demo.clerk.accounts.dev"
        return {"sub": "user_clerk_123"}

    monkeypatch.setenv("CLERK_JWT_ISSUER", issuer)
    monkeypatch.setattr(clerk, "_jwks_client", lambda value: _FakeJwksClient())
    monkeypatch.setattr(clerk.jwt, "decode", fake_decode)

    user = clerk.verify_clerk_token("jwt")

    assert user.user_id == "user_clerk_123"
    assert user.token == "jwt"
    assert len(calls) == 2
