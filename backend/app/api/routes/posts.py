from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import get_current_user
from app.core.context import ApplicationContext
from app.core.logging import get_logger
from app.models.post import PostRecord
from app.models.schemas import (
    ApprovalRequest,
    FormattingPrefs,
    GenerateRequest,
    PostEditSuggestions,
    PublishRequest,
    RecordStatusCounts,
    RegenerateRequest,
    ReworkRequest,
    SuggestOutput,
    SuggestRequest,
    SuggestResponse,
    UpdatePostRequest,
)
from app.models.user import LinkedInUser

logger = get_logger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])


def ctx(request: Request) -> ApplicationContext:
    return request.app.state.app_ctx


def _require_owner(record: Optional[PostRecord], owner_id: str) -> PostRecord:
    if record is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if record.owner_id and record.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="This post belongs to another user.")
    return record


# ─── helpers ──────────────────────────────────────────────────
def _apply_generated(record: PostRecord, state: dict) -> None:
    record.topic = state.get("topic", record.topic)
    record.audience = state.get("audience", record.audience)
    record.content_angle = state.get("content_angle", record.content_angle)
    record.priority = state.get("priority", record.priority)
    record.post_type = state.get("post_type", record.post_type)
    record.language = state.get("language", record.language)
    record.generated_post = state.get("generated_post", record.generated_post)
    record.hashtags = list(state.get("hashtags") or record.hashtags)
    record.image_prompt = state.get("image_prompt", record.image_prompt)
    record.image_url = state.get("image_url")
    record.image_provider = state.get("image_provider", record.image_provider)
    record.text_model = state.get("text_model", record.text_model)
    record.validation_status = state.get("validation_status", record.validation_status)
    record.validation_result = state.get("validation_result", {})
    record.review_status = "READY_FOR_REVIEW"
    record.generation_status = "GENERATED"
    record.record_status = "READY_FOR_REVIEW"


def _apply_publish(record: PostRecord, state: dict) -> None:
    record.review_status = "APPROVED"
    record.approval_status = "APPROVED"
    record.publishing_status = state.get("publishing_status", record.publishing_status)
    record.linkedin_post_id = state.get("linkedin_post_id")
    record.google_sheet_status = state.get("google_sheet_status", record.google_sheet_status)
    record.error = state.get("publish_error")
    record.record_status = (
        "PUBLISHED" if record.publishing_status == "PUBLISHED" else "FAILED"
    )


def _state_from_record(record: PostRecord) -> dict:
    return {
        "record_id": record.record_id,
        "owner_id": record.owner_id,
        "user_query": record.user_query,
        "priority": record.priority,
        "post_type": record.post_type,
        "language": record.language,
        "topic": record.topic,
        "audience": record.audience,
        "content_angle": record.content_angle,
        "generated_post": record.generated_post,
        "edited_post": record.final_post or record.generated_post,
        "hashtags": record.hashtags,
        "image_prompt": record.image_prompt,
        "image_url": record.image_url,
        "image_provider": record.image_provider,
        "text_model": record.text_model,
        "validation_result": record.validation_result,
        "validation_status": record.validation_status,
    }


def _flush(record: PostRecord, request: Request) -> PostRecord:
    request.app.state.app_ctx.store.update(record.record_id)
    return record


# ─── suggest ──────────────────────────────────────────────────
@router.post("/suggest")
async def suggest_query(
    req: SuggestRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> SuggestResponse:
    """Rewrite the user's topic into a sharper question (live composer assist)."""
    app_ctx = ctx(request)
    provider = app_ctx.text_provider
    improved = req.text.strip()
    note = "kept as written"
    try:
        result: SuggestOutput = await provider.structured(
            SuggestOutput,
            (
                "You are a LinkedIn content strategist. Rewrite the user's raw topic or "
                "question into ONE sharper, more specific, searchable question for a post "
                "generator. Make the intent and who it's for obvious; keep it under 220 "
                "characters. Add a note (max ~8 words) saying what you sharpened, e.g. "
                "'names the audience', 'adds the outcome', 'crisper wording'. Return strict JSON."
            ),
            "User's raw topic:\n{text}",
            text=req.text,
        )
        candidate = (result.improved or "").strip()
        if 3 <= len(candidate) <= 500:
            improved = candidate
            note = (result.note or "").strip() or "sharpened"
    except Exception as exc:  # noqa: BLE001
        logger.warning("suggest failed, returning original", error=str(exc), user_id=user.user_id)
    return SuggestResponse(original=req.text, improved=improved, note=note)


@router.post("/{record_id}/suggest-edits")
async def suggest_edits(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostEditSuggestions:
    """LLM editing suggestions for a generated post: notes + an improved draft."""
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)
    if not rec.generated_post:
        raise HTTPException(status_code=400, detail="Post has no generated text yet.")

    from app.prompts.edit_suggestions import EDIT_HUMAN, EDIT_SYSTEM

    try:
        result: PostEditSuggestions = await app_ctx.text_provider.structured(
            PostEditSuggestions,
            EDIT_SYSTEM,
            EDIT_HUMAN,
            topic=rec.topic or "",
            audience=rec.audience or "",
            post=rec.final_post or rec.generated_post,
            hashtags=" ".join(rec.hashtags or []),
        )
        return PostEditSuggestions(
            summary=result.summary,
            notes=list(result.notes)[:6],
            improved_draft=result.improved_draft or rec.final_post or rec.generated_post,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("edit suggestions failed", record_id=record_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Edit suggestions failed: {exc}")


# ─── generate ─────────────────────────────────────────────────
@router.post("/generate", status_code=201)
async def generate_post(
    req: GenerateRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    app_ctx = ctx(request)
    record = PostRecord(user_query=req.user_query, owner_id=user.user_id)
    app_ctx.store.create(record)
    logger.info("generation started", record_id=record.record_id, owner_id=user.user_id)

    try:
        seed: dict = {}
        if req.priority:
            seed["priority"] = req.priority
        if req.post_type:
            seed["post_type"] = req.post_type
        seed["language"] = (req.language or "English").strip() or "English"
        seed["formatting"] = req.formatting.model_dump()
        state = await app_ctx.workflow.run_generation(
            req.user_query, record.record_id, user=user, seed=seed or None
        )
        _apply_generated(record, state)
        record.touch("GENERATED")
        return _flush(record, request)
    except Exception as exc:  # noqa: BLE001
        logger.error("generation failed", record_id=record.record_id, error=str(exc))
        record.record_status = "FAILED"
        record.error = str(exc)
        record.touch("GENERATION_FAILED")
        _flush(record, request)
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")


# ─── rework with suggestions ─────────────────────────────────
@router.post("/{record_id}/rework")
async def rework_post_route(
    record_id: str,
    req: ReworkRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    """Apply the edit-suggestions draft + formatting toggles: rewrite, fresh
    hashtags, re-validation. Keeps the existing image."""
    from app.agents.nodes.content_nodes import rework_post

    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)
    text = (req.text or "").strip() or rec.final_post or rec.generated_post
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="Draft is too short to rework.")

    try:
        result = await rework_post(
            app_ctx.node_context,
            topic=rec.topic,
            audience=rec.audience,
            language=rec.language,
            draft=text,
            formatting=req.formatting.model_dump(),
            user_query=rec.user_query,
        )
        rec.generated_post = result["generated_post"]
        rec.hashtags = list(result["hashtags"])
        rec.validation_result = result["validation_result"]
        rec.validation_status = result["validation_status"]
        rec.text_model = result["text_model"]
        rec.language = result["language"]
        rec.final_post = None
        rec.review_status = "READY_FOR_REVIEW"
        rec.generation_status = "GENERATED"
        rec.record_status = "READY_FOR_REVIEW"
        rec.error = None
        rec.touch("REWORKED")
        return _flush(rec, request)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("rework failed", record_id=record_id, error=str(exc))
        rec.error = f"Rework failed: {exc}"
        rec.touch("REWORK_FAILED")
        _flush(rec, request)
        raise HTTPException(status_code=502, detail=f"Rework failed: {exc}")


# ─── read ─────────────────────────────────────────────────────
@router.get("")
async def list_posts(
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    priority: Optional[str] = None,
    post_type: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    app_ctx = ctx(request)
    records = app_ctx.store.list(
        owner_id=user.user_id,
        limit=limit,
        offset=offset,
        priority=priority,
        post_type=post_type,
        status=status,
    )
    all_records = app_ctx.store.all(owner_id=user.user_id)
    counts = {
        "total": len(all_records),
        "ready_for_review": sum(1 for r in all_records if r.record_status == "READY_FOR_REVIEW"),
        "published": sum(1 for r in all_records if r.record_status == "PUBLISHED"),
        "failed": sum(1 for r in all_records if r.record_status == "FAILED"),
    }
    return {"items": records, "counts": RecordStatusCounts(**counts)}


@router.get("/{record_id}")
async def get_post(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    rec = _require_owner(ctx(request).store.get(record_id), user.user_id)
    return rec


# ─── edit ─────────────────────────────────────────────────────
@router.put("/{record_id}")
async def update_post(
    record_id: str,
    req: UpdatePostRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    rec.final_post = req.final_post
    if req.hashtags is not None:
        rec.hashtags = [h if h.startswith("#") else f"#{h}" for h in req.hashtags]
    rec.review_status = "READY_FOR_REVIEW"
    rec.record_status = "EDITED" if rec.record_status not in ("PUBLISHED", "FAILED") else rec.record_status
    if rec.record_status == "PUBLISHED":
        # LinkedIn does not allow editing a live ugcPost, so a revision to a
        # published post is re-queued and republished as a new post.
        rec.approval_status = "APPROVED"
        rec.publishing_status = "INITIALIZED"
        rec.linkedin_post_id = None
        rec.record_status = "EDITED"
        rec.touch("REVISION_SAVED")
    else:
        rec.touch("EDITED")
    return _flush(rec, request)


# ─── regenerate ───────────────────────────────────────────────
@router.post("/{record_id}/regenerate")
async def regenerate_post(
    record_id: str,
    req: RegenerateRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    from app.agents.nodes.content_nodes import (
        analyze_topic,
        generate_hashtags,
        generate_linkedin_post,
        plan_content,
        validate_content,
    )

    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    node_ctx = app_ctx.node_context
    topic_changed = bool(req.user_query and req.user_query != rec.user_query)

    try:
        if topic_changed:
            rec.user_query = req.user_query
            thread = f"{record_id}:regen-{_atomic()}"
            state = await app_ctx.workflow.run_generation(req.user_query, thread, user=user)
            _apply_generated(rec, state)
            rec.final_post = None
            rec.touch("REGENERATED_FULL")
        else:
            base = _state_from_record(rec)
            state = await analyze_topic(base, node_ctx)
            base.update(state)
            state = await plan_content(base, node_ctx)
            base.update(state)
            state = await generate_linkedin_post(base, node_ctx)
            base.update(state)
            state = await generate_hashtags(base, node_ctx)
            base.update(state)
            state = await validate_content(base, node_ctx)
            base.update(state)
            _apply_generated(rec, base)
            rec.final_post = None
            rec.touch("REGENERATED_TEXT")
        return _flush(rec, request)
    except Exception as exc:  # noqa: BLE001
        logger.error("regeneration failed", record_id=record_id, error=str(exc))
        rec.record_status = "FAILED"
        rec.error = str(exc)
        _flush(rec, request)
        raise HTTPException(status_code=502, detail=f"Regeneration failed: {exc}")


# ─── regenerate image only ────────────────────────────────────
@router.post("/{record_id}/regenerate-image")
async def regenerate_image(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    from app.agents.nodes.content_nodes import generate_image, generate_image_prompt

    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    node_ctx = app_ctx.node_context
    try:
        base = _state_from_record(rec)
        if not rec.image_prompt:
            state = await generate_image_prompt(base, node_ctx)
            base.update(state)
            rec.image_prompt = base["image_prompt"]
        state = await generate_image(base, node_ctx)
        rec.image_url = state.get("image_url")
        rec.image_provider = state.get("image_provider", rec.image_provider)
        rec.touch("IMAGE_REGENERATED")
        return _flush(rec, request)
    except Exception as exc:  # noqa: BLE001
        logger.error("image regeneration failed", record_id=record_id, error=str(exc))
        rec.error = f"Image regeneration failed: {exc}"
        _flush(rec, request)
        raise HTTPException(status_code=502, detail=f"Image regeneration failed: {exc}")


# ─── approve (human in the loop) ──────────────────────────────
@router.post("/{record_id}/approve")
async def approve_post(
    record_id: str,
    req: ApprovalRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    if not req.approved:
        rec.review_status = "REJECTED"
        rec.approval_status = "NOT_APPROVED"
        rec.record_status = rec.record_status if rec.record_status == "EDITED" else "READY_FOR_REVIEW"
        rec.touch("REJECTED")
        return _flush(rec, request)

    try:
        state = await app_ctx.workflow.approve_and_publish(
            record_id,
            approved=True,
            resume_update={
                "edited_post": rec.final_post or rec.generated_post,
                "hashtags": rec.hashtags,
                "user_approved": True,
            },
        )
        _apply_publish(rec, state)
        rec.final_post = rec.final_post or state.get("edited_post") or rec.generated_post
        rec.touch("APPROVED_PUBLISHED" if rec.publishing_status == "PUBLISHED" else "APPROVED_PUBLISH_FAILED")
        return _flush(rec, request)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("approval/publish failed", record_id=record_id, error=str(exc))
        rec.error = str(exc)
        rec.review_status = "READY_FOR_REVIEW"
        rec.record_status = "FAILED"
        rec.touch("APPROVAL_FAILED")
        _flush(rec, request)
        raise HTTPException(status_code=502, detail=f"Publish failed: {exc}")


# ─── publish (retry-safe) ─────────────────────────────────────
@router.post("/{record_id}/publish")
async def publish_post(
    record_id: str,
    req: PublishRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    if rec.approval_status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail="Post must be manually approved before publishing.",
        )

    if rec.publishing_status == "PUBLISHED":
        return rec

    state = await app_ctx.workflow.retry_publish(_state_from_record(rec), user=user)
    _apply_publish(rec, state)
    rec.touch("PUBLISH_RETRY")
    return _flush(rec, request)


def _atomic() -> str:
    import uuid

    return uuid.uuid4().hex[:6]


__all__ = ["router"]