"""LinkedIn posting guidelines the agent follows (public, read-only)."""
from __future__ import annotations

from fastapi import APIRouter

from app.prompts.guidelines import guidelines_payload

router = APIRouter(prefix="/api", tags=["guidelines"])


@router.get("/guidelines")
def get_guidelines():
    return guidelines_payload()


__all__ = ["router"]
