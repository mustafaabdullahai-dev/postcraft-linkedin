"""Abuse + cost controls: real client IP, rate limiting, daily paid-call quotas.

Two independent layers:
  * `RateLimiter`  — per-IP sliding window, in-process, cheap first line.
  * `DailyQuota`   — per-user and whole-app daily ceilings on paid AI calls,
                     persisted to `data/usage.json` so restarts don't reset it.

Both are disabled when their configured limit is 0.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from fastapi import Depends, HTTPException, Request

from app.core.auth import get_current_user
from app.models.user import LinkedInUser


# ─── real client IP behind a trusted proxy ────────────────────
def _is_trusted(ip: str, trusted: Sequence[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in trusted:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def client_ip(request: Request, trusted: Sequence[str]) -> str:
    """Return the original client IP, honouring X-Forwarded-For only when the
    direct peer is a trusted proxy (otherwise a client could spoof its IP)."""
    peer = request.client.host if request.client else "unknown"
    if not trusted or not _is_trusted(peer, trusted):
        return peer
    for header in ("x-forwarded-for", "x-real-ip"):
        raw = request.headers.get(header, "")
        if raw:
            candidate = raw.split(",")[0].strip()
            if candidate:
                return candidate
    return peer


# ─── per-IP sliding-window rate limiter ───────────────────────
class RateLimiter:
    def __init__(self, per_minute: int = 6, max_keys: int = 20_000):
        self._per_minute = per_minute
        self._max_keys = max_keys
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> Tuple[bool, int]:
        if self._per_minute <= 0:
            return True, 0
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < 60.0]
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > self._max_keys:
                self._prune(now)
            return (len(hits) <= self._per_minute, self._per_minute)

    def _prune(self, now: float) -> None:
        stale = [k for k, v in self._hits.items() if not v or now - v[-1] >= 60.0]
        for k in stale:
            self._hits.pop(k, None)


# ─── persisted daily paid-call quotas ─────────────────────────
def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class DailyQuota:
    """Per-user + global daily counters, atomically persisted to JSON."""

    def __init__(
        self,
        data_dir: Path,
        *,
        per_user_generations: int = 0,
        per_user_images: int = 0,
        global_calls: int = 0,
    ):
        self._path = Path(data_dir) / "usage.json"
        self._lock = threading.RLock()
        self.per_user_generations = per_user_generations
        self.per_user_images = per_user_images
        self.global_calls = global_calls
        self._state = {"date": _utc_day(), "users": {}, "global": 0}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("date") == _utc_day():
                self._state = {
                    "date": raw["date"],
                    "users": raw.get("users", {}) if isinstance(raw.get("users"), dict) else {},
                    "global": int(raw.get("global", 0)),
                }
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    def _flush(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def _rollover(self) -> None:
        today = _utc_day()
        if self._state.get("date") != today:
            self._state = {"date": today, "users": {}, "global": 0}

    def check_and_consume(self, user_id: str, kind: str = "generation") -> Tuple[bool, str]:
        with self._lock:
            self._rollover()
            per_user = (
                self.per_user_images if kind == "image" else self.per_user_generations
            )
            user = self._state["users"].setdefault(user_id, {})
            used = int(user.get(kind, 0))

            if per_user and used >= per_user:
                return False, f"Daily {kind} limit reached ({per_user}/day). Try again tomorrow."
            if self.global_calls and self._state["global"] >= self.global_calls:
                return False, "The service has hit its daily capacity. Please try again tomorrow."

            user[kind] = used + 1
            self._state["global"] = int(self._state["global"]) + 1
            try:
                self._flush()
            except OSError:
                pass  # never fail a request on a metrics write
            return True, ""


# ─── FastAPI dependency factory ───────────────────────────────
def ai_quota(kind: str):
    """Dependency: authenticate the user AND charge one paid call.

    Use in place of `Depends(get_current_user)` on any route that costs money.
    """

    def dependency(
        request: Request, user: LinkedInUser = Depends(get_current_user)
    ) -> LinkedInUser:
        quota = getattr(request.app.state.app_ctx, "quota", None)
        if quota is not None:
            ok, reason = quota.check_and_consume(user.user_id, kind)
            if not ok:
                raise HTTPException(status_code=429, detail=reason)
        return user

    return dependency


__all__ = ["RateLimiter", "DailyQuota", "client_ip", "ai_quota"]
