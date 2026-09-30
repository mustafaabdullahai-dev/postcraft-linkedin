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

# One "emoji" = a base pictograph (optionally followed by variation selectors,
# skin-tone or ZWJ-joined parts) OR a keycap sequence (digit + U+FE0F + U+20E3).
# The previous range skipped U+20E3, so numbered keycap list markers were
# invisible to the counter: a post could show 8 emoji while validating as 3.
_EMOJI_BASE = (
    "\U0001F000-\U0001FAFF"  # pictographs, symbols, supplemental, ext-A
    "\u2600-\u27BF"          # misc symbols + dingbats
    "\u2B00-\u2BFF"          # arrows / geometric shapes
    "\uFE00-\uFE0F"          # variation selectors
    "\u200D"                        # zero-width joiner (family / rainbow)
    "\U0001F3FB-\U0001F3FF"  # skin-tone modifiers
)
_KEYCAP = "[0-9#*]\\uFE0F?\\u20E3"
_EMOJI_RI = "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
_EMOJI_MOD = "\uFE00-\uFE0F\U0001F3FB-\U0001F3FF"
# One cluster = base + modifiers, plus any ZWJ-joined parts (a family counts
# once). Adjacent emoji stay separate matches because nothing joins them.
_EMOJI_CLUSTER = f"[{_EMOJI_BASE}][{_EMOJI_MOD}]*"
# A base emoji plus any ZWJ-joined parts = ONE emoji (a family is 1, not 5).
# Adjacent emoji stay separate because nothing joins them. The leading base is
# required so the pattern can never match an empty string (empty matches would
# make findall() report an emoji per character).
_EMOJI_FLAG = f"[{_EMOJI_RI}](?:[{_EMOJI_MOD}]*[{_EMOJI_RI}])+[{_EMOJI_MOD}]*"
EMOJI_RE = re.compile(
    f"{_EMOJI_FLAG}|{_EMOJI_CLUSTER}(?:\\u200D{_EMOJI_CLUSTER})+|{_EMOJI_CLUSTER}|{_KEYCAP}",
    re.UNICODE,
)
# Two or more keycap markers on the SAME line = a crammed numbered list.
# The separator is any non-newline text: a real list reads "1️⃣ a 2️⃣ b".
KEYCAP_RUN_RE = re.compile(f"(?:{_KEYCAP}[^\n]*){{2,}}")


def count_emojis(text: str) -> int:
    """Count emoji as a reader sees them; keycaps and ZWJ parts count once."""
    return len(EMOJI_RE.findall(text or ""))


METRIC_RE = re.compile(r"\b(?:\d+(?:\.\d+)?\s*(?:%|percent|x|×)\b|\$\d[\dk+]*|\d{3,}x)")
HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")

LINE_BEGIN_EMOJI_RE = re.compile(f"^\\s*(?:[{_EMOJI_BASE}]|{_KEYCAP})")

# LinkedIn discourages engagement bait; flag the common phrasings.
ENGAGEMENT_BAIT = [
    re.compile(r"\b(?:like|smash like|hit like)\b[^.\n]{0,20}\bif you\b", re.IGNORECASE),
    re.compile(r"\bcomment\s+[\"“']?(?:yes|agree|done|1)\b", re.IGNORECASE),
    re.compile(r"\btag\s+(?:a|your|two|three)\s+(?:friend|colleague|colleagues|people)", re.IGNORECASE),
    re.compile(r"\bfollow\s+(?:me\s+)?for\s+(?:more|follow)", re.IGNORECASE),
    re.compile(r"\b(?:share|repost)\s+this\s+(?:if|to)\b", re.IGNORECASE),
]


class ValidationRules:
    def __init__(self, post: str, hashtags: List[str], emojis_enabled: bool = True):
        self.post = post
        self.hashtags = [h for h in hashtags if isinstance(h, str)]
        # Mirrors FormattingPrefs.emojis: when the user turns emojis off, any
        # emoji in the draft is a defect rather than a missing one.
        self.emojis_enabled = emojis_enabled

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

        # Numbered keycap lists (1️⃣ 2️⃣ …) packed onto one line read as a wall of
        # text on mobile; each step belongs on its own line.
        if any(KEYCAP_RUN_RE.search(line) for line in bean_lines):
            issues.append(
                "Numbered keycap steps (1️⃣ 2️⃣ …) are crammed into one line; put each step on its own line"
            )

        # count_emojis() sees keycaps, flags, VS16 and ZWJ clusters the way a
        # reader does; the old regex missed keycaps, so a post showing 8 emoji
        # could validate as 3.
        emoji_count = count_emojis(self.post)
        if not self.emojis_enabled and emoji_count:
            # Turning emojis off is an explicit user choice, so stray emoji is a
            # defect. A merely-low count stays advisory (see style_suggestions).
            issues.append(f"Emojis present ({emoji_count}) although the emoji toggle is off")
        if emoji_count > 12:
            issues.append(f"Too many emojis ({emoji_count}); target 3-7")

        # ── safety / claims
        if METRIC_RE.search(post) and not _metric_allowed_context(post):
            issues.append("Unsupported metric/statistic found (e.g. percentages without citation)")

        for c in CLICHES:
            if c in low:
                issues.append(f"AI cliché: '{c}'")

        for bait in ENGAGEMENT_BAIT:
            if bait.search(low):
                issues.append("Engagement bait detected (LinkedIn discourages it)")
                break

        # ── hashtags
        tags = self.hashtags
        if not (5 <= len(tags) <= 10):
            issues.append(f"Hashtag count {len(tags)}; target 5-10")
        if len(post) < 300:
            issues.append("Post too short (<300 chars)")
        if len(post) > 3000:
            issues.append("Post exceeds 3000 chars (LinkedIn limit ~3000)")

        return issues

    def style_suggestions(self) -> List[str]:
        """Non-blocking style notes about emoji usage.

        Emoji density is a house-style preference, not a correctness rule, so
        it must not invalidate a post (the mock/demo provider emits no emoji at
        all). These notes still surface in the validation panel.
        """
        out: List[str] = []
        count = count_emojis(self.post)
        if not self.emojis_enabled:
            return out
        if count < 3:
            out.append(
                f"Only {count} emoji in the post; the house style is 3-7 total, "
                "sprinkled inline (never at the start of a line)."
            )
        elif count > 7:
            out.append(f"{count} emoji is above the 3-7 target; trim the extras.")
        return out

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
        emojis_enabled: bool = True,
    ) -> ValidationOutput:
        rules = ValidationRules(post, hashtags, emojis_enabled=emojis_enabled)
        blocking = rules.blocking_issues()

        issues = list(blocking)
        suggestions: List[str] = list(rules.style_suggestions())

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