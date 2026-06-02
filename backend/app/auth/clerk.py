import os
from functools import lru_cache
from urllib.parse import urlparse

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    user_id: str
    token: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must be Bearer <token>",
        )
    return token


def _validate_issuer(issuer: str) -> str:
    configured = os.getenv("CLERK_JWT_ISSUER")
    if configured:
        if issuer != configured:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer",
            )
        return issuer

    parsed = urlparse(issuer)
    allowed_hosts = ("clerk.accounts.dev", "accounts.clerk.com")
    if parsed.scheme != "https" or not any(
        parsed.hostname == host or parsed.hostname.endswith(f".{host}")
        for host in allowed_hosts
        if parsed.hostname
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
        )
    return issuer


@lru_cache(maxsize=8)
def _jwks_client(issuer: str) -> PyJWKClient:
    return PyJWKClient(f"{issuer}/.well-known/jwks.json")


def verify_clerk_token(token: str) -> AuthenticatedUser:
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer = _validate_issuer(str(unverified.get("iss", "")))
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk token",
        ) from exc

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk token missing subject",
        )
    return AuthenticatedUser(user_id=str(user_id), token=token)


def current_user(authorization: str | None = Header(None)) -> AuthenticatedUser:
    return verify_clerk_token(_extract_bearer_token(authorization))
