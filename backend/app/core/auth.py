"""Session authentication: signed session tokens + FastAPI dependency."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import LinkedInUser, UserStore

logger = get_logger(__name__)

SESSION_COOKIE = "session"
MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(get_settings().secret_key, salt="auth")


def create_session_token(user_id: str) -> str:
    return _serializer.dumps(user_id)


def verify_session_token(token: str) -> Optional[str]:
    try:
        return _serializer.loads(token, max_age=MAX_AGE)  # type: ignore[arg-type]
    except (BadSignature, SignatureExpired):
        return None


def user_store(request: Request) -> UserStore:
    return request.app.state.app_ctx.user_store


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> LinkedInUser:
    """Resolve the logged-in user from `Authorization: Bearer <token>` or the
    `session` cookie (set by the LinkedIn OAuth callback)."""
    store = user_store(request)
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get(SESSION_COOKIE)

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = verify_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = store.get(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")

    return user


__all__ = [
    "create_session_token",
    "verify_session_token",
    "get_current_user",
    "SESSION_COOKIE",
    "MAX_AGE",
]