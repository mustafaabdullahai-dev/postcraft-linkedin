"""LinkedIn engagement analytics.

Real mode reads social-activities counts from the LinkedIn API for a published
post's URN. Mock/dry-run mode returns deterministic, believable sample data so
the dashboard works end-to-end without a live token.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict
from urllib.request import Request, urlopen

from app.core.logging import get_logger

logger = get_logger(__name__)

_SOCIAL_ACTIONS = "/v2/socialActions/{urn}"


class EngagementAnalytics:
    def __init__(self, linkedin_publisher=None, dry_run: bool = True):
        self.publisher = linkedin_publisher
        self.dry_run = dry_run

    @property
    def real_configured(self) -> bool:
        return not self.dry_run and self.publisher is not None and self.publisher.oauth_configured()

    def baseline(self, record_id: str) -> Dict[str, Any]:
        """Deterministic mock engagement (used when live data isn't available)."""
        seed = int(hashlib.sha1(record_id.encode()).hexdigest(), 16)
        likes = 8 + seed % 120
        comments = 2 + seed % 25
        shares = 1 + seed % 18
        impressions = likes * 9 + comments * 23 + shares * 30 + 150
        return {
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "impressions": impressions,
            "source": "sample",
            "fetched_at": None,
        }

    async def fetch(self, record_id: str, linkedin_post_urn: str, access_token: str = "") -> Dict[str, Any]:
        if not self.real_configured or not linkedin_post_urn:
            return self.baseline(record_id)
        try:
            data = await self._request(linkedin_post_urn, access_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("linkedin analytics fetch failed", urn=linkedin_post_urn, error=str(exc))
            return self.baseline(record_id)
        return {
            "likes": self._count(data, "likeSummary"),
            "comments": self._count(data, "commentSummary"),
            "shares": self._count(data, "shareSummary"),
            "impressions": 0,
            "source": "linkedin",
            "fetched_at": None,
        }

    def _count(self, data: dict, key: str) -> int:
        summary = data.get(key) or {}
        return int(summary.get("totalGreaterThan") or summary.get("total") or 0)

    async def _request(self, urn: str, access_token: str) -> dict:
        from app.services.linkedin import LINKEDIN_API

        url = LINKEDIN_API + _SOCIAL_ACTIONS.format(urn=urn)
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        with urlopen(req, timeout=15) as res:  # noqa: S310 - host is pinned
            return json.loads(res.read().decode("utf-8"))


class MockEngagement(EngagementAnalytics):
    """Explicit mock (used when providers are in mock mode)."""


__all__ = ["EngagementAnalytics", "MockEngagement"]