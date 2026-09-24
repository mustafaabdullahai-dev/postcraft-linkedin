"""Persistent post record model + JSON-backed repository."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.schemas import (
    ApprovalStatus,
    GenerationStatus,
    ReviewStatus,
    ValidationStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_record_id() -> str:
    stamp = _now().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"{stamp}-{suffix}"


class PostRecord(BaseModel):
    record_id: str = Field(default_factory=new_record_id)
    user_query: str
    owner_id: str = ""

    topic: str = ""
    audience: str = ""
    content_angle: str = ""

    priority: str = "Medium"
    post_type: str = "Insights"
    # Language chosen by the user for this post's text and its image wording.
    language: str = "English"

    generated_post: str = ""
    final_post: Optional[str] = None
    hashtags: List[str] = Field(default_factory=list)

    image_prompt: str = ""
    image_negative_prompt: str = ""
    image_url: Optional[str] = None
    image_provider: str = ""

    text_model: str = ""

    validation_status: str = ValidationStatus.PENDING.value
    validation_result: Dict[str, Any] = Field(default_factory=dict)

    review_status: str = ReviewStatus.PENDING.value
    approval_status: str = ApprovalStatus.NOT_APPROVED.value
    generation_status: str = GenerationStatus.INITIALIZED.value
    publishing_status: str = GenerationStatus.INITIALIZED.value

    linkedin_post_id: Optional[str] = None
    google_sheet_status: str = "NOT_LOGGED"

    record_status: str = GenerationStatus.INITIALIZED.value

    # Scheduling: future publish moment chosen at approval time. When set and
    # record_status == "SCHEDULED", the background scheduler publishes on due.
    scheduled_at: Optional[datetime] = None
    # When the post actually went live (set on successful publish).
    published_at: Optional[datetime] = None
    # Engagement snapshot for published posts: {likes, comments, shares,
    # impressions, fetched_at} — refreshed from the LinkedIn socialActions API.
    analytics: Dict[str, Any] = Field(default_factory=dict)
    # Brand voice preset applied at generation time (name kept for history).
    voice_profile_id: Optional[str] = None
    voice_profile_name: str = ""

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    error: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)

    def touch(self, event: Optional[str] = None) -> None:
        self.updated_at = _now()
        if event:
            self.history.append(
                {"event": event, "at": _now().isoformat()}
            )


class PostStore:
    """Thread-safe JSON-file backed repository.

    No external database is required for local development. Swap this class
    for a SQLAlchemy/Postgres implementation in production — the API only
    depends on the small method surface below.
    """

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "posts.json"
        self._lock = threading.RLock()
        self._cache: Dict[str, PostRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in raw.get("records", []):
            try:
                rec = PostRecord.model_validate(item)
                self._cache[rec.record_id] = rec
            except Exception:
                continue

    def _flush(self) -> None:
        payload = {
            "records": [r.model_dump(mode="json") for r in self._cache.values()]
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self._path)

    # ── CRUD ──────────────────────────────────────────────
    def create(self, record: PostRecord) -> PostRecord:
        with self._lock:
            record.touch("CREATED")
            self._cache[record.record_id] = record
            self._flush()
            return record

    def get(self, record_id: str) -> Optional[PostRecord]:
        with self._lock:
            return self._cache.get(record_id)

    def _matches(
        self,
        rec: PostRecord,
        owner_id: str = "",
        priority: Optional[str] = None,
        post_type: Optional[str] = None,
        status: Optional[str] = None,
        q: str = "",
        from_date: str = "",
        to_date: str = "",
    ) -> bool:
        query = q.strip().lower()
        if owner_id and rec.owner_id != owner_id:
            return False
        if priority and rec.priority != priority:
            return False
        if post_type and rec.post_type != post_type:
            return False
        if status and rec.record_status != status:
            return False
        if query:
            haystack = " ".join(
                [
                    rec.user_query,
                    rec.topic,
                    rec.generated_post,
                    rec.final_post or "",
                    " ".join(rec.hashtags),
                    rec.record_id,
                ]
            ).lower()
            if query not in haystack:
                return False
        if from_date or to_date:
            # Calendar date = scheduled → published → created (first available).
            ref = rec.scheduled_at or rec.published_at or rec.created_at
            if ref is None:
                return False
            if from_date:
                try:
                    lo = datetime.fromisoformat(from_date)
                    lo = lo if lo.tzinfo else lo.replace(tzinfo=timezone.utc)
                    if ref < lo:
                        return False
                except ValueError:
                    pass
            if to_date:
                try:
                    hi = datetime.fromisoformat(to_date)
                    hi = hi if hi.tzinfo else hi.replace(tzinfo=timezone.utc)
                    # to_date is inclusive to the end of that day.
                    if ref > hi.replace(hour=23, minute=59, second=59, microsecond=999999):
                        return False
                except ValueError:
                    pass
        return True

    def list(
        self,
        owner_id: str = "",
        limit: int = 50,
        offset: int = 0,
        priority: Optional[str] = None,
        post_type: Optional[str] = None,
        status: Optional[str] = None,
        q: str = "",
        sort: str = "newest",
        from_date: str = "",
        to_date: str = "",
    ) -> List[PostRecord]:
        with self._lock:
            matches: List[PostRecord] = []
            for rec in self._cache.values():
                if self._matches(
                    rec, owner_id, priority, post_type, status, q, from_date, to_date
                ):
                    matches.append(rec)
            matches.sort(
                key=lambda r: r.updated_at,
                reverse=sort != "oldest",
            )
            return matches[offset : offset + limit]

    def delete_all(
        self,
        owner_id: str = "",
        priority: Optional[str] = None,
        post_type: Optional[str] = None,
        status: Optional[str] = None,
        q: str = "",
    ) -> int:
        """Bulk-delete every non-published post matching the filters.

        Published posts are kept as the user's public track record.
        """
        with self._lock:
            doomed = [
                rec.record_id
                for rec in self._cache.values()
                if rec.record_status != "PUBLISHED"
                and self._matches(rec, owner_id, priority, post_type, status, q)
            ]
            for record_id in doomed:
                del self._cache[record_id]
            if doomed:
                self._flush()
            return len(doomed)

    def delete(self, record_id: str) -> bool:
        with self._lock:
            if record_id not in self._cache:
                return False
            del self._cache[record_id]
            self._flush()
            return True

    def update(self, record_id: str, event: Optional[str] = None, **fields: Any) -> Optional[PostRecord]:
        with self._lock:
            rec = self._cache.get(record_id)
            if rec is None:
                return None
            for k, v in fields.items():
                setattr(rec, k, v)
            rec.touch(event)
            self._flush()
            return rec

    def all(self, owner_id: str = "") -> List[PostRecord]:
        with self._lock:
            if not owner_id:
                return list(self._cache.values())
            return [r for r in self._cache.values() if r.owner_id == owner_id]


__all__ = ["PostRecord", "PostStore", "new_record_id"]