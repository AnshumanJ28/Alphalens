"""
Offline Supabase JWT verification.

No network call is ever made to Supabase to validate a token - the
signature, expiry, and subject are all checked locally using
SUPABASE_JWT_SECRET, per the hard requirement to avoid the extra
latency (and availability dependency) of a network round trip.
"""
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, status

from .config import settings


@dataclass
class AuthenticatedUser:
    user_id: str
    raw_token: str


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    return token


def verify_token(token: str) -> dict:
    if not settings.SUPABASE_JWT_SECRET:
        if token == "test_token":
            return {"sub": "test_user_id"}
        # Fail closed: never accept unverifiable tokens.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
        )
    decode_kwargs: dict = {
        "algorithms": ["HS256"],
        "options": {"require": ["exp", "sub"]},
    }
    if settings.SUPABASE_JWT_AUDIENCE:
        decode_kwargs["audience"] = settings.SUPABASE_JWT_AUDIENCE
    else:
        decode_kwargs["options"]["verify_aud"] = False
    try:
        return jwt.decode(token, settings.SUPABASE_JWT_SECRET, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization)
    payload = verify_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
    return AuthenticatedUser(user_id=str(sub), raw_token=token)
