"""Health / readiness checks."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    app_ctx = request.app.state.app_ctx
    s = app_ctx.settings
    return HealthResponse(
        status="ok",
        environment=s.environment,
        text_provider=app_ctx.text_provider.name,
        image_provider=app_ctx.image_provider.name,
        linkedin_mode=app_ctx.linkedin_publisher.mode(),
        sheets_mode=app_ctx.sheets_service.mode(),
        linkedin_configured=app_ctx.linkedin_publisher.oauth_configured(),
    )


__all__ = ["router"]