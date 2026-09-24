"""Per-user LinkedIn connection status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user
from app.core.logging import get_logger
from app.models.user import LinkedInUser

logger = get_logger(__name__)
router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])


@router.get("/status")
def linkedin_status(request: Request, user: LinkedInUser = Depends(get_current_user)):
    p = request.app.state.app_ctx.linkedin_publisher
    return {
        "mode": p.mode(),
        "oauth_configured": p.oauth_configured(),
        "connected": user.connected,
        "expires_at": user.token_expires_at.isoformat() if user.token_expires_at else None,
    }


__all__ = ["router"]