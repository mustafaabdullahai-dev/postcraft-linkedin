"""Auth endpoints: LinkedIn OAuth login, guest (demo) login, session.

Open-source flow:
1. "Sign in with LinkedIn" → /api/auth/linkedin/login → LinkedIn consent →
   callback stores the user + tokens → httpOnly `session` cookie →
   redirect back to the frontend.
2. "Continue as guest" → /api/auth/guest → Bearer token (demo mode).
3. /api/auth/me is the single source of truth the frontend boots against.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.auth import MAX_AGE, SESSION_COOKIE, create_session_token, get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import LinkedInUser, UserStore

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def publisher(request: Request):
    return request.app.state.app_ctx.linkedin_publisher


def users(request: Request) -> UserStore:
    return request.app.state.app_ctx.user_store


def linkedin_redirect_uri() -> str:
    s = get_settings()
    if s.linkedin_redirect_uri:
        return s.linkedin_redirect_uri
    return f"{s.frontend_url.rstrip('/')}/api/auth/linkedin/callback"


def _signed_state(remember: bool = True) -> str:
    payload = (
        f"{secrets.token_urlsafe(12)}:"
        f"{int(datetime.now(timezone.utc).timestamp())}:"
        f"{'1' if remember else '0'}"
    )
    return create_session_token(payload)


def _verify_state(state: str):
    """Returns None if invalid, else (ok: bool, remember: bool)."""
    from app.core.auth import verify_session_token

    token = verify_session_token(state)
    if not token:
        return None
    try:
        _, ts, remember = token.rsplit(":", 2)
        if (int(datetime.now(timezone.utc).timestamp()) - int(ts)) >= 600:
            return None
        return True, remember == "1"
    except (ValueError, AttributeError):
        return None


def _profile_picture(profile: dict) -> str:
    # OIDC userinfo usually returns `picture` directly; fall back to the
    # classic r_liteprofile displayImage structure if present.
    if profile.get("picture"):
        return profile["picture"]
    streams = (
        profile.get("profilePicture", {}).get("displayImage~", {}).get("elements", [])
    )
    if not streams:
        return ""
    try:
        return streams[-1]["identifiers"][0]["identifier"]
    except (IndexError, KeyError, TypeError):
        return ""


def _user_from_profile(profile: dict, email: str, token_data: dict) -> LinkedInUser:
    # OIDC "Sign in with LinkedIn" userinfo shape:
    #   {sub, name, given_name, family_name, picture, email, email_verified}
    linkedin_id = profile.get("sub", "") or profile.get("id", "")
    given = profile.get("given_name", "")
    family = profile.get("family_name", "")
    name = profile.get("name") or f"{given} {family}".strip() or "LinkedIn User"
    expires_in = int(token_data.get("expires_in", 0))
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
    )
    return LinkedInUser(
        linkedin_sub=linkedin_id,
        name=name,
        headline=profile.get("headline", ""),
        picture_url=_profile_picture(profile),
        email=email or profile.get("email", ""),
        urn=f"urn:li:person:{linkedin_id}" if linkedin_id else "",
        access_token=token_data.get("access_token", ""),
        refresh_token=token_data.get("refresh_token", ""),
        token_expires_at=expires_at,
        is_guest=False,
    )


# ─── LinkedIn OAuth ───────────────────────────────────────────
@router.get("/linkedin/login")
def linkedin_login(request: Request, remember: bool = Query(default=True)):
    p = publisher(request)
    if not p.oauth_configured():
        raise HTTPException(
            status_code=400,
            detail="LinkedIn OAuth is not configured (set LINKEDIN_CLIENT_ID/SECRET).",
        )
    state = _signed_state(remember)
    url = p.authorize_url(state=state, redirect_uri=linkedin_redirect_uri())
    return RedirectResponse(url=url)


@router.get("/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
):
    if error or not code:
        logger.warning(
            "linkedin oauth error received",
            error=error,
            error_description=error_description,
        )
        raise HTTPException(status_code=400, detail=error_description or error or "No code")
    verified = _verify_state(state)
    if not verified:
        logger.warning("linkedin oauth state mismatch", state_len=len(state))
        raise HTTPException(status_code=400, detail="OAuth state mismatch — please retry.")
    _, remember = verified

    p = publisher(request)
    try:
        token_data = await p.exchange_code(code, linkedin_redirect_uri())
        profile = await p.me(token_data.get("access_token", ""))
    except Exception as exc:  # noqa: BLE001
        logger.error("linkedin token exchange failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"LinkedIn login failed: {exc}") from exc

    store = users(request)
    incoming = _user_from_profile(profile, profile.get("email", ""), token_data)
    existing = store.find_by_linkedin(incoming.linkedin_sub) if incoming.linkedin_sub else None
    user = existing if existing else LinkedInUser(linkedin_sub=incoming.linkedin_sub)
    for field in ("name", "headline", "picture_url", "email", "urn",
                  "access_token", "refresh_token", "token_expires_at"):
        setattr(user, field, getattr(incoming, field))
    store.save(user)

    token = create_session_token(user.user_id)
    logger.info("user logged in via linkedin", user_id=user.user_id, remember=remember)
    frontend = get_settings().frontend_url
    response = RedirectResponse(url=f"{frontend.rstrip('/')}/?auth=linkedin")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=MAX_AGE if remember else None,
        httponly=True,
        secure=get_settings().is_production,
        samesite="lax",
    )
    return response


class GuestRequest(BaseModel):
    name: str = Field(default="", max_length=80)


# ─── Guest / session ──────────────────────────────────────────
def _guest(request: Request, body: Optional[GuestRequest] = None) -> JSONResponse:
    store = users(request)
    user = store.create_guest(name=body.name if body else "")
    token = create_session_token(user.user_id)
    logger.info("guest session created", user_id=user.user_id)
    return JSONResponse(content={"token": token, "user": _public_user(user)})


@router.post("/guest")
async def guest_login_route(body: GuestRequest, request: Request):
    return _guest(request, body)


@router.get("/me")
def me(user: LinkedInUser = Depends(get_current_user)):
    return _public_user(user)


@router.post("/logout")
def logout():
    response = JSONResponse(content={"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


def _public_user(user: LinkedInUser) -> dict:
    return {
        "user_id": user.user_id,
        "name": user.name,
        "headline": user.headline,
        "picture_url": user.picture_url,
        "email": user.email,
        "is_guest": user.is_guest,
        "connected": user.connected,
        "created_at": user.created_at.isoformat(),
    }


__all__ = ["router"]