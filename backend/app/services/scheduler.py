"""Background scheduler: publishes approved posts when their scheduled time hits."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.graph import LinkedInWorkflow
from app.core.context import ApplicationContext
from app.core.logging import get_logger
from app.models.post import PostRecord

logger = get_logger(__name__)

POLL_SECONDS = 20


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
    }


def _due(app_ctx: ApplicationContext, now: datetime) -> list[PostRecord]:
    out = []
    for rec in app_ctx.store.all():
        if (
            rec.record_status == "SCHEDULED"
            and rec.scheduled_at is not None
            and rec.scheduled_at <= now
        ):
            out.append(rec)
    return out


async def _publish_one(app_ctx: ApplicationContext, rec: PostRecord) -> None:
    workflow: LinkedInWorkflow = app_ctx.workflow
    a_ctx = app_ctx
    try:
        result = await workflow.retry_publish(_state_from_record(rec))
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduled publish crashed", record_id=rec.record_id, error=str(exc))
        rec.record_status = "FAILED"
        rec.error = str(exc)
        rec.publishing_status = "FAILED"
        rec.touch("SCHEDULED_PUBLISH_FAILED")
        a_ctx.store.update(rec.record_id)
        return

    rec.publishing_status = result.get("publishing_status", "PUBLISHED")
    rec.linkedin_post_id = result.get("linkedin_post_id") or rec.linkedin_post_id
    rec.google_sheet_status = result.get("google_sheet_status", rec.google_sheet_status)
    rec.error = result.get("publish_error")
    if rec.publishing_status == "PUBLISHED":
        rec.record_status = "PUBLISHED"
        rec.published_at = datetime.now(timezone.utc)
        rec.analytics = a_ctx.engagement.baseline(rec.record_id)
        rec.touch("SCHEDULED_PUBLISHED")
    else:
        rec.record_status = "FAILED"
        rec.touch("SCHEDULED_PUBLISH_FAILED")
    a_ctx.store.update(rec.record_id)


async def run_once(app_ctx: ApplicationContext) -> int:
    now = datetime.now(timezone.utc)
    due = _due(app_ctx, now)
    for rec in due:
        logger.info("scheduled publish firing", record_id=rec.record_id)
        await _publish_one(app_ctx, rec)
    return len(due)


async def scheduler_loop(app_ctx: ApplicationContext) -> None:
    logger.info("scheduler started", interval_seconds=POLL_SECONDS)
    while True:
        try:
            published = await run_once(app_ctx)
            if published:
                logger.info("scheduled posts published", count=published)
        except Exception as exc:  # noqa: BLE001
            logger.error("scheduler tick error", error=str(exc))
        await asyncio.sleep(POLL_SECONDS)


__all__ = ["scheduler_loop", "run_once", "POLL_SECONDS"]