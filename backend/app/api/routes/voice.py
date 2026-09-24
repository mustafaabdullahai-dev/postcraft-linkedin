"""Brand-voice preset CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user
from app.core.context import ApplicationContext
from app.models.schemas import VoiceProfile, VoiceProfileCreate, VoiceProfileUpdate
from app.models.voice import VoiceProfileStore

router = APIRouter(prefix="/api/voice-profiles", tags=["voice"])


def _store(request: Request) -> VoiceProfileStore:
    app_ctx: ApplicationContext = request.app.state.app_ctx
    return app_ctx.voice_store


@router.get("")
async def list_profiles(request: Request, user=Depends(get_current_user)) -> list[VoiceProfile]:
    return _store(request).list()


@router.post("", status_code=201)
async def create_profile(
    req: VoiceProfileCreate,
    request: Request,
    user=Depends(get_current_user),
) -> VoiceProfile:
    return _store(request).create(req)


@router.put("/{voice_id}")
async def update_profile(
    voice_id: str,
    req: VoiceProfileUpdate,
    request: Request,
    user=Depends(get_current_user),
) -> VoiceProfile:
    updated = _store(request).update(voice_id, req)
    if updated is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return updated


@router.delete("/{voice_id}")
async def delete_profile(
    voice_id: str,
    request: Request,
    user=Depends(get_current_user),
) -> dict:
    if not _store(request).delete(voice_id):
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return {"ok": True, "voice_id": voice_id}


__all__ = ["router"]