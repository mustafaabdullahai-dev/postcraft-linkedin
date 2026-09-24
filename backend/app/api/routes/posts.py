from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.core.auth import get_current_user
from app.core.context import ApplicationContext
from app.core.logging import get_logger
from app.models.post import PostRecord
from app.models.schemas import (
    ApprovalRequest,
    GenerateRequest,
    PostEditSuggestions,
    PublishRequest,
    RecordStatusCounts,
    RegenerateImageRequest,
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

MANUAL_IMAGE_NEGATIVE = (
    "misspelled or gibberish text, wrong-language text, watermarks, logos, "
    "unrelated objects, low quality, blurry, duplicate of a previous concept"
)


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


def _mark_published(app_ctx, record: PostRecord) -> None:
    """Stamp published_at + baseline engagement on successfully published posts."""
    if record.publishing_status == "PUBLISHED":
        if record.published_at is None:
            record.published_at = datetime.now(timezone.utc)
        if not record.analytics:
            record.analytics = app_ctx.engagement.baseline(record.record_id)


def _voice_seed(app_ctx, voice_profile_id: str, formatting: dict) -> dict:
    """Merge a brand-voice preset into the generation seed."""
    profile = app_ctx.voice_store.get(voice_profile_id)
    if profile is None:
        return {"voice_profile_id": None, "voice_profile_name": "", "formatting": formatting}
    fmt = dict(formatting)
    if profile.word_target:
        fmt["word_target"] = profile.word_target
    for key in ("emojis", "bullets", "short_paragraphs", "practitioner_story", "discussion_cta"):
        value = getattr(profile, key)
        if value is not None:
            fmt[key] = value
    if profile.tone or profile.audience:
        fmt["voice_note"] = f"{profile.name}: tone {profile.tone}; audience {profile.audience}".replace("  ", " ")
    else:
        fmt["voice_note"] = profile.name
    return {
        "voice_profile_id": profile.voice_id,
        "voice_profile_name": profile.name,
        "formatting": fmt,
    }


def _base_seed(app_ctx, req) -> dict:
    """Common generate/batch seed (minus the LLM-affecting notes)."""
    seed: dict = {}
    if req.priority:
        seed["priority"] = req.priority
    if req.post_type:
        seed["post_type"] = req.post_type
    seed["language"] = (req.language or "English").strip() or "English"
    seed["formatting"] = req.formatting.model_dump()
    if req.voice_profile_id:
        seed.update(_voice_seed(app_ctx, req.voice_profile_id, seed["formatting"]))
    return seed


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

    seed = _base_seed(app_ctx, req)
    try:
        state = await app_ctx.workflow.run_generation(
            req.user_query, record.record_id, user=user, seed=seed or None
        )
        _apply_generated(record, state)
        record.voice_profile_id = seed.get("voice_profile_id")
        record.voice_profile_name = seed.get("voice_profile_name", "")
        record.touch("GENERATED")
        return _flush(record, request)
    except Exception as exc:  # noqa: BLE001
        logger.error("generation failed", record_id=record.record_id, error=str(exc))
        record.record_status = "FAILED"
        record.error = str(exc)
        record.touch("GENERATION_FAILED")
        _flush(record, request)
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}")


# ─── batch generate (variations) ──────────────────────────────
@router.post("/batch-generate", status_code=201)
async def batch_generate(
    req: GenerateRequest,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> dict:
    """Generate 2-3 distinct drafts for the same topic; the user picks their
    favourite. Each draft is its own post record so it stays fully editable."""
    app_ctx = ctx(request)
    variations = max(1, min(3, req.variations))
    items: list[PostRecord] = []
    for i in range(variations):
        record = PostRecord(user_query=req.user_query, owner_id=user.user_id)
        app_ctx.store.create(record)
        seed = _base_seed(app_ctx, req)
        if variations > 1:
            note = (
                f"draft {i + 1} of {variations}: use a clearly different hook, angle and "
                "structure from the other drafts — vary the metaphor and the opening line "
                "(keep the topic the same and stay factually accurate)"
            )
            seed.setdefault("formatting", {})["variant_note"] = note
        try:
            state = await app_ctx.workflow.run_generation(
                req.user_query, record.record_id, user=user, seed=seed or None
            )
            _apply_generated(record, state)
            record.voice_profile_id = seed.get("voice_profile_id")
            record.voice_profile_name = seed.get("voice_profile_name", "")
            record.touch("GENERATED")
            app_ctx.store.update(record.record_id)
        except Exception as exc:  # noqa: BLE001 — keep the failed slot, let siblings succeed
            logger.error("variant generation failed", record_id=record.record_id, error=str(exc))
            record.record_status = "FAILED"
            record.error = str(exc)
            record.touch("GENERATION_FAILED")
            app_ctx.store.update(record.record_id)
        items.append(record)
    return {"items": items}


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
    q: Optional[str] = None,
    sort: str = "newest",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    app_ctx = ctx(request)
    records = app_ctx.store.list(
        owner_id=user.user_id,
        limit=limit,
        offset=offset,
        priority=priority,
        post_type=post_type,
        status=status,
        q=q or "",
        sort=sort,
        from_date=from_date or "",
        to_date=to_date or "",
    )
    all_records = app_ctx.store.all(owner_id=user.user_id)
    counts = {
        "total": len(all_records),
        "ready_for_review": sum(1 for r in all_records if r.record_status == "READY_FOR_REVIEW"),
        "scheduled": sum(1 for r in all_records if r.record_status == "SCHEDULED"),
        "published": sum(1 for r in all_records if r.record_status == "PUBLISHED"),
        "failed": sum(1 for r in all_records if r.record_status == "FAILED"),
    }
    return {
        "items": records,
        "counts": RecordStatusCounts(**counts),
        "total": len(all_records),
    }


# ─── insights ─────────────────────────────────────────────────
@router.get("/insights")
async def post_insights(
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> dict:
    """Engagement dashboard aggregates over the user's published posts."""
    app_ctx = ctx(request)
    posts = [
        r for r in app_ctx.store.all(owner_id=user.user_id)
        if r.record_status == "PUBLISHED"
    ]
    totals = {"posts": len(posts), "likes": 0, "comments": 0, "shares": 0, "impressions": 0}
    top: Optional[dict] = None
    for rec in posts:
        a = rec.analytics or {}
        likes = int(a.get("likes") or 0)
        comments = int(a.get("comments") or 0)
        shares = int(a.get("shares") or 0)
        impressions = int(a.get("impressions") or 0)
        totals["likes"] += likes
        totals["comments"] += comments
        totals["shares"] += shares
        totals["impressions"] += impressions
        score = likes + comments * 3 + shares * 5
        if top is None or score > top["score"]:
            top = {
                "score": score,
                "record_id": rec.record_id,
                "title": rec.user_query or rec.topic or rec.record_id,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "published_at": rec.published_at.isoformat() if rec.published_at else None,
            }
    all_records = app_ctx.store.all(owner_id=user.user_id)
    overview = {
        "total": len(all_records),
        "ready_for_review": sum(1 for r in all_records if r.record_status == "READY_FOR_REVIEW"),
        "scheduled": sum(1 for r in all_records if r.record_status == "SCHEDULED"),
        "published": sum(1 for r in all_records if r.record_status == "PUBLISHED"),
        "failed": sum(1 for r in all_records if r.record_status == "FAILED"),
    }
    return {
        "totals": totals,
        "top": top,
        "overview": overview,
        "last_refreshed": datetime.now(timezone.utc).isoformat(),
    }


# ─── export ───────────────────────────────────────────────────
@router.get("/export")
async def export_posts(
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
    format: str = "json",
) -> Response:
    app_ctx = ctx(request)
    posts = sorted(
        app_ctx.store.all(owner_id=user.user_id),
        key=lambda r: r.created_at,
    )
    fmt = (format or "json").lower()

    if fmt == "csv":
        body = _export_csv(posts)
        media = "text/csv"
    elif fmt == "md":
        body = _export_markdown(posts)
        media = "text/markdown"
    elif fmt == "json":
        body = io.StringIO(
            json.dumps(
                {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "count": len(posts),
                    "posts": [p.model_dump(mode="json") for p in posts],
                },
                indent=2,
                default=str,
            )
        )
        media = "application/json"
    else:
        raise HTTPException(status_code=400, detail="format must be csv, json or md")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=body.getvalue() if isinstance(body, io.StringIO) else body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="posts-{stamp}.{fmt}"'},
    )


def _export_csv(posts) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "record_id", "status", "priority", "post_type", "language",
            "user_query", "topic", "audience", "content_angle", "voice",
            "created_at", "scheduled_at", "published_at",
            "final_post", "generated_post", "hashtags", "image_url",
            "likes", "comments", "shares", "impressions", "linkedin_post_id",
        ]
    )
    for p in posts:
        a = p.analytics or {}
        writer.writerow(
            [
                p.record_id, p.record_status, p.priority, p.post_type, p.language,
                p.user_query, p.topic, p.audience, p.content_angle, p.voice_profile_name,
                p.created_at.isoformat() if p.created_at else "",
                p.scheduled_at.isoformat() if p.scheduled_at else "",
                p.published_at.isoformat() if p.published_at else "",
                p.final_post or "", p.generated_post, " ".join(p.hashtags), p.image_url or "",
                int(a.get("likes") or 0), int(a.get("comments") or 0),
                int(a.get("shares") or 0), int(a.get("impressions") or 0),
                p.linkedin_post_id or "",
            ]
        )
    return out.getvalue()


def _export_markdown(posts) -> str:
    lines = ["# PostCraft export", "", f"Total posts: {len(posts)}", ""]
    for p in posts:
        body = p.final_post or p.generated_post
        lines.append(f"## {p.record_id} — {p.record_status}")
        lines.append("")
        lines.append(f"**Topic:** {p.user_query or p.topic or '-'}")
        lines.append(f"**Priority:** {p.priority}  **Type:** {p.post_type}  **Voice:** {p.voice_profile_name or '-'}")
        lines.append("")
        lines.append(body)
        if p.hashtags:
            lines.append("")
            lines.append(" ".join(p.hashtags))
        lines.append("")
    return "\n".join(lines)


@router.get("/{record_id}")
async def get_post(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    rec = _require_owner(ctx(request).store.get(record_id), user.user_id)
    return rec


# ─── delete ───────────────────────────────────────────────────
@router.delete("")
async def delete_all_posts(
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
    priority: Optional[str] = None,
    post_type: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    """Bulk delete every non-published post matching the filters."""
    app_ctx = ctx(request)
    deleted = app_ctx.store.delete_all(
        owner_id=user.user_id,
        priority=priority,
        post_type=post_type,
        status=status,
        q=q or "",
    )
    return {"ok": True, "deleted": deleted}


@router.delete("/{record_id}")
async def delete_post(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> dict:
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)
    if rec.record_status == "PUBLISHED":
        raise HTTPException(
            status_code=409,
            detail="Published posts can't be deleted — keep them as your public track record",
        )
    removed = app_ctx.store.delete(record_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True, "record_id": record_id}


# ─── duplicate (start a new draft from this) ──────────────────
@router.post("/{record_id}/duplicate")
async def duplicate_post(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    from datetime import datetime, timezone

    from app.models.post import new_record_id

    app_ctx = ctx(request)
    original = _require_owner(app_ctx.store.get(record_id), user.user_id)

    copy = original.model_copy(deep=True)
    now = datetime.now(timezone.utc)
    copy.record_id = new_record_id()
    copy.owner_id = user.user_id
    # Fresh lifecycle — never carries over publish/audit state.
    copy.record_status = "INITIALIZED"
    copy.review_status = "PENDING"
    copy.approval_status = "NOT_APPROVED"
    copy.generation_status = "INITIALIZED"
    copy.publishing_status = "INITIALIZED"
    copy.validation_status = "PENDING"
    copy.validation_result = {}
    copy.linkedin_post_id = None
    copy.google_sheet_status = "NOT_LOGGED"
    copy.image_url = None
    copy.image_provider = ""
    copy.image_prompt = ""
    copy.image_negative_prompt = ""
    copy.error = None
    copy.created_at = now
    copy.updated_at = now
    copy.history = []
    copy.touch("CREATED")
    return app_ctx.store.create(copy)


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
    body: Optional[RegenerateImageRequest] = None,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    from app.agents.nodes.content_nodes import generate_image, regenerate_image_prompt

    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)

    node_ctx = app_ctx.node_context
    try:
        base = _state_from_record(rec)
        prompt = (body.prompt if body else None) or ""
        if prompt.strip():
            # Manual prompt: use exactly what the user typed, skip the LLM.
            base["image_prompt"] = prompt.strip()
            base["image_negative_prompt"] = rec.image_negative_prompt or MANUAL_IMAGE_NEGATIVE
        else:
            # Art-director re-roll: a senior creative persona designs a
            # COMPLETELY different concept for the same topic.
            state = await regenerate_image_prompt(base, node_ctx)
            base.update(state)
        state = await generate_image(base, node_ctx)
        rec.image_prompt = base.get("image_prompt", rec.image_prompt)
        rec.image_negative_prompt = base.get("image_negative_prompt", rec.image_negative_prompt)
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

    if req.scheduled_at is not None:
        scheduled = req.scheduled_at
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Pick a future time to publish.")
        rec.review_status = "APPROVED"
        rec.approval_status = "APPROVED"
        rec.publishing_status = "SCHEDULED"
        rec.record_status = "SCHEDULED"
        rec.scheduled_at = scheduled
        rec.error = None
        rec.touch("APPROVED_SCHEDULED")
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
        _mark_published(app_ctx, rec)
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
        _mark_published(app_ctx, rec)
        return _flush(rec, request)

    state = await app_ctx.workflow.retry_publish(_state_from_record(rec), user=user)
    _apply_publish(rec, state)
    _mark_published(app_ctx, rec)
    rec.touch("PUBLISH_RETRY")
    return _flush(rec, request)


# ─── engagement analytics ─────────────────────────────────────
@router.post("/{record_id}/refresh-analytics")
async def refresh_analytics(
    record_id: str,
    request: Request,
    user: LinkedInUser = Depends(get_current_user),
) -> PostRecord:
    """Pull fresh like/comment/share counts for a published post."""
    app_ctx = ctx(request)
    rec = _require_owner(app_ctx.store.get(record_id), user.user_id)
    if rec.record_status != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Only published posts have engagement data.")
    token = user.access_token or ""
    result = await app_ctx.engagement.fetch(rec.record_id, rec.linkedin_post_id or "", token)
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    rec.analytics = result
    rec.touch("ANALYTICS_REFRESHED")
    return _flush(rec, request)


def _atomic() -> str:
    import uuid

    return uuid.uuid4().hex[:6]


__all__ = ["router"]