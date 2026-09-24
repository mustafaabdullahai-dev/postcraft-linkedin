"""Registered user model + JSON-backed store.

Open-source multi-user design:
- Every user logs in with LinkedIn (OAuth) OR continues as a guest in demo mode.
- Posts are scoped per user (owner_id); publishing uses the *logged-in user's*
  LinkedIn token/URN, never a shared credential.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LinkedInUser(BaseModel):
    user_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    linkedin_sub: str = ""  # ORCID-style LinkedIn profile id (empty for guests)
    name: str = ""
    headline: str = ""
    picture_url: str = ""
    email: str = ""
    urn: str = ""  # e.g. urn:li:person:XXXX used for publishing

    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: Optional[datetime] = None

    is_guest: bool = False

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @property
    def connected(self) -> bool:
        return bool(self.urn and self.access_token)

    def touch(self) -> None:
        self.updated_at = _now()


class UserStore:
    """Thread-safe JSON-file backed repository (data/users.json)."""

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "users.json"
        self._lock = threading.RLock()
        self._cache: Dict[str, LinkedInUser] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in raw.get("users", []):
            try:
                user = LinkedInUser.model_validate(item)
                self._cache[user.user_id] = user
            except Exception:
                continue

    def _flush(self) -> None:
        payload = {"users": [u.model_dump(mode="json") for u in self._cache.values()]}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self._path)

    # ── CRUD ──────────────────────────────────────────────────
    def get(self, user_id: str) -> Optional[LinkedInUser]:
        with self._lock:
            return self._cache.get(user_id)

    def find_by_linkedin(self, linkedin_sub: str) -> Optional[LinkedInUser]:
        with self._lock:
            for u in self._cache.values():
                if u.linkedin_sub and u.linkedin_sub == linkedin_sub:
                    return u
            return None

    def save(self, user: LinkedInUser) -> LinkedInUser:
        with self._lock:
            user.touch()
            self._cache[user.user_id] = user
            self._flush()
            return user

    def create_guest(self, name: str = "") -> LinkedInUser:
        user = LinkedInUser(name=name or "Guest User", is_guest=True)
        return self.save(user)


__all__ = ["LinkedInUser", "UserStore"]