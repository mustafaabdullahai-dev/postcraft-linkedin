"""Deterministic content validation (rules) + LLM advisory quality score.

Blocking rules are decided by code, not by the model, so a flaky LLM response
can never silently let a fabricated claim or broken format through. The LLM
only supplies the quality score and subjective suggestions.
"""
from __future__ import annotations

import re
from typing import List, Optional

from app.core.logging import get_logger
from app.models.schemas import ValidationOutput

logger = get_logger(__name__)

CLICHES = [
    "in today's rapidly evolving world",
    "in today's fast-paced",
    "game-changer",
    "gamechanger",
    "delve",
    "unleash",
    "revolutionize the way",
    "it's important to note",
    "the ever-evolving landscape",
    "unlock the power",
    "stay ahead of the curve",
]

SECTION_HEADERS = [
    "hook", "problem", "technical insight", "engineering perspective",
    "practical takeaways", "takeaways", "conclusion", "cta",
]

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2600-\u27BF]",
    re.UNICODE,
)
METRIC_RE = re.compile(r"\b(?:\d+(?:\.\d+)?\s*(?:%|percent|x|×)\b|\$\d[\dk+]*|\d{3,}x)")
HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")
LINE_BEGIN_EMOJI_RE = re.compile(r"^\s*[\U0001F000-\U0001FAFF\u2600-\u27BF]")


class ValidationRules:
    def __init__(self, post: str, hashtags: List[str]):
        self.post = post
        self.hashtags = [h for h in hashtags if isinstance(h, str)]

    def blocking_issues(self) -> List[str]:
        issues: List[str] = []
        post = self.post or ""
        low = post.lower()

        # ── structure / formatting
        for h in SECTION_HEADERS:
            if re.search(rf"^{re.escape(h)}\s*[:⏎]?", low, re.IGNORECASE | re.MULTILINE):
                issues.append(f"Literal section header '{h}' found in published text")
        if re.search(r"^#?\s*hashtags\s*:", low, re.MULTILINE | re.IGNORECASE):
            issues.append("A 'Hashtags:' label line is present; only a single tag line is allowed")
        if post.count('"""') or re.search(r"```", post):
            issues.append("Code fences found in post")

        bean_lines = [line for line in post.splitlines() if line.strip()]
        if bean_lines and sum(1 for line in bean_lines if LINE_BEGIN_EMOJI_RE.match(line)) > max(1, len(bean_lines) // 3):
            issues.append("Emojis start too many lines (max ~1/3 of lines)")

        emoji_count = len(EMOJI_RE.findall(post))
        if emoji_count > 12:
            issues.append(f"Too many emojis ({emoji_count}); target 3-7")

        # ── safety / claims
        if METRIC_RE.search(post) and not _metric_allowed_context(post):
            issues.append("Unsupported metric/statistic found (e.g. percentages without citation)")

        for c in CLICHES:
            if c in low:
                issues.append(f"AI cliché: '{c}'")

        # ── hashtags
        tags = self.hashtags
        if not (5 <= len(tags) <= 10):
            issues.append(f"Hashtag count {len(tags)}; target 5-10")
        if len(post) < 300:
            issues.append("Post too short (<300 chars)")
        if len(post) > 3000:
            issues.append("Post exceeds 3000 chars (LinkedIn limit ~3000)")

        return issues

    def has_inline_hashtags(self) -> int:
        return len(set(HASHTAG_RE.findall(self.post)))


def _metric_allowed_context(post: str) -> bool:
    # A metric is acceptable only if explicitly framed as hypothetical/generic
    # ("e.g.", "say", "roughly", "approximately", "such as").
    ctx = re.search(
        r"\(?(e\.g\.|e.g.,?|say|say,|roughly|approximately|for example[^)]*)\s*\d",
        post,
        re.IGNORECASE,
    )
    return bool(ctx)


class ContentValidator:
    def __init__(self, text_provider=None):
        self._text_provider = text_provider

    async def validate(
        self,
        post: str,
        hashtags: List[str],
        user_query: str,
    ) -> ValidationOutput:
        rules = ValidationRules(post, hashtags)
        blocking = rules.blocking_issues()

        issues = list(blocking)
        suggestions: List[str] = []

        score = 1.0
        if self._text_provider is not None:
            try:
                from app.models.schemas import ValidationOutput as _VO
                from app.prompts.validation import VALIDATION_HUMAN, VALIDATION_SYSTEM

                advisory: Optional[ValidationOutput] = None
                advisory = await self._text_provider.structured(
                    _VO,
                    VALIDATION_SYSTEM,
                    VALIDATION_HUMAN,
                    user_query=user_query,
                    post=post,
                    hashtags=" ".join(hashtags),
                )
                score = advisory.quality_score
                # Advisory issues are NOT merged into `issues`: blocking rules
                # above are deterministic; advisory output is only used for the
                # quality score and subjective suggestions.
                suggestions += advisory.suggestions[:3]
            except Exception as exc:  # noqa: BLE001
                logger.warning("advisory LLM validation failed", error=str(exc))
                score = 0.8

        if blocking:
            score = min(score, 0.5)
        valid = not blocking

        return ValidationOutput(
            valid=valid,
            quality_score=round(score, 2),
            issues=issues[:8],
            suggestions=suggestions[:3],
        )


__all__ = ["ContentValidator", "ValidationRules"]