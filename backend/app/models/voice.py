"""Reusable brand-voice presets: stored per-owner in a JSON file."""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.schemas import VoiceProfile, VoiceProfileCreate, VoiceProfileUpdate

_FOLDER = "voice_profiles.json"

DEFAULT_PROFILES: List[Dict[str, Any]] = [
    {
        "name": "Trusted Founder",
        "description": "Warm, credible, big-picture. Great for leadership and personal-brand posts.",
        "tone": "confident, warm, first-person founder voice with one clear opinion",
        "audience": "founders, operators and senior leaders who value practical experience over hype",
        "word_target": 0,
    },
    {
        "name": "Deep Tech Explainer",
        "description": "Precise and technical, still readable. Use for engineering and product content.",
        "tone": "precise, technical but human, jargon explained in one line",
        "audience": "engineers, technical leads and data professionals",
        "word_target": 0,
    },
    {
        "name": "Coach / Practical How-To",
        "description": "Step-by-step and actionable. Perfect for teaching posts and playbooks.",
        "tone": "instructive, encouraging, action-first with a single clear takeaway",
        "audience": "professionals looking for concrete steps they can apply today",
        "word_target": 0,
        "bullets": True,
        "practitioner_story": True,
    },
]


def new_voice_id() -> str:
    return "v-" + uuid.uuid4().hex[:8]


class VoiceProfileStore:
    """Thread-safe JSON-file repository for brand-voice presets."""

    def __init__(self, data_dir: str | Path):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _FOLDER
        self._lock = threading.RLock()
        self._cache: Dict[str, VoiceProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._seed()
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._seed()
            return
        for item in raw.get("profiles", []):
            try:
                profile = VoiceProfile.model_validate(item)
                self._cache[profile.voice_id] = profile
            except Exception:
                continue

    def _seed(self) -> None:
        for item in DEFAULT_PROFILES:
            profile = VoiceProfile(voice_id=new_voice_id(), is_default=True, **item)
            self._cache[profile.voice_id] = profile
        self._flush()

    def _flush(self) -> None:
        payload = {"profiles": [p.model_dump() for p in self._cache.values()]}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self._path)

    def list(self) -> List[VoiceProfile]:
        with self._lock:
            return list(self._cache.values())

    def get(self, voice_id: str) -> Optional[VoiceProfile]:
        with self._lock:
            return self._cache.get(voice_id)

    def create(self, data: VoiceProfileCreate) -> VoiceProfile:
        profile = VoiceProfile(voice_id=new_voice_id(), **data.model_dump())
        with self._lock:
            self._cache[profile.voice_id] = profile
            self._flush()
        return profile

    def update(self, voice_id: str, data: VoiceProfileUpdate) -> Optional[VoiceProfile]:
        with self._lock:
            profile = self._cache.get(voice_id)
            if profile is None:
                return None
            changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
            updated = profile.model_copy(update=changes)
            self._cache[voice_id] = updated
            self._flush()
            return updated

    def delete(self, voice_id: str) -> bool:
        with self._lock:
            if voice_id not in self._cache:
                return False
            del self._cache[voice_id]
            self._flush()
            return True


__all__ = ["VoiceProfileStore", "new_voice_id", "DEFAULT_PROFILES"]