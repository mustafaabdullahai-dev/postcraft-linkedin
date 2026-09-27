"""Authenticated access to user-uploaded post images.

Uploaded images are *not* served as public static files: a request must carry a
valid session (Bearer token or cookie) and, when the image belongs to a post,
must come from that post's owner. The frontend loads them with `fetch()` +
Authorization so token-based sessions work too.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.core.auth import get_current_user
from app.models.user import LinkedInUser

router = APIRouter(tags=["uploads"])

_SAFE_NAME = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-_")


@router.get("/uploads/{name}")
def get_upload(
    name: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
):
    """Serve one uploaded image to its owner only."""
    if not name or not name.endswith(".jpg") or any(c not in _SAFE_NAME for c in name):
        raise HTTPException(status_code=404, detail="Not found")

    app_ctx = request.app.state.app_ctx
    uploads = app_ctx.data_dir / "uploads"
    path = (uploads / name).resolve()
    if uploads.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    # Authorise against the post that references this file (if any), so one user
    # can never read another user's uploaded photo by guessing a filename.
    owner = None
    for rec in app_ctx.store.all():
        if (rec.image_url or "").endswith(f"/{name}"):
            owner = rec.owner_id
            break
    if owner is not None and owner != user.user_id:
        raise HTTPException(status_code=403, detail="Not your image")

    return FileResponse(path, media_type="image/jpeg")


__all__ = ["router"]
