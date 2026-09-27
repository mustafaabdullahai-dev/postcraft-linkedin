"""LinkedIn posting guidelines the agent follows for text and image output.

Single source of truth. The writer/validator prompts encode these rules and
`GET /api/guidelines` exposes the same list so the UI can show exactly what is
enforced — keeping the documentation and the behaviour in sync.
"""
from __future__ import annotations

from typing import Any, Dict, List

Guideline = Dict[str, str]

TEXT_GUIDELINES: List[Guideline] = [
    {
        "title": "Length fits LinkedIn",
        "detail": "300–3000 characters (LinkedIn's hard limit). The writer targets 700–1300 for reach.",
    },
    {
        "title": "Strong, specific hook",
        "detail": "The first line is a concrete field observation — never a cliché or a question.",
    },
    {
        "title": "Practitioner structure",
        "detail": "Hook → problem → insight → practitioner perspective → takeaways → conclusion → CTA, written as flowing prose with no literal section labels.",
    },
    {
        "title": "Short, scannable paragraphs",
        "detail": "1–3 sentences per paragraph.",
    },
    {
        "title": "Emojis used sparingly",
        "detail": "3–7 in total, sprinkled inline. Never an emoji at the start of a line.",
    },
    {
        "title": "Bold only for key terms",
        "detail": "**bold** marks a few genuinely important terms (1–2 per paragraph), never whole sentences.",
    },
    {
        "title": "Bullets only for lists",
        "detail": "• lines are reserved for takeaways/enumerations; no other bullet characters.",
    },
    {
        "title": "5–10 relevant hashtags",
        "detail": "Fresh for each post, tied to its niche/industry/audience, placed on the final line. No fixed, personal or brand tags. Non-Latin scripts keep hashtags in English.",
    },
    {
        "title": "Natural call to action",
        "detail": "A contextual discussion prompt — never a bare “Thoughts?”.",
    },
    {
        "title": "Requested language only",
        "detail": "The entire post — hook, body, bullets, CTA and hashtags — is written in the chosen language, with no mixed-language words.",
    },
]

SAFETY_GUIDELINES: List[Guideline] = [
    {
        "title": "No fabricated facts",
        "detail": "No invented employers, customers, projects, credentials, statistics or metrics. Zero-data claims are framed as general practice (“from what I've seen…”).",
    },
    {
        "title": "No AI clichés",
        "detail": "Banned: “game-changer”, “delve”, “unleash”, “in today's rapidly evolving world”, “unlock the power”, “stay ahead of the curve” and similar filler.",
    },
    {
        "title": "No engagement bait",
        "detail": "No “like if you agree”, “comment ‘YES’”, “tag a friend”, fake urgency or follow-for-follow.",
    },
    {
        "title": "No misleading claims",
        "detail": "No unsupported absolutes or advice framed as guaranteed. No medical, legal or financial promises.",
    },
    {
        "title": "Professional and safe",
        "detail": "No hate, harassment, discrimination, adult content or anything violating LinkedIn's Professional Community Policies.",
    },
    {
        "title": "Clean formatting",
        "detail": "No code fences, no stray unclosed asterisks, no “Hashtags:” label line, no duplicated tag lines.",
    },
]

IMAGE_GUIDELINES: List[Guideline] = [
    {
        "title": "Unique concept per post",
        "detail": "A fresh visual metaphor built for this specific topic and angle — never a recycled stock “AI/tech” template.",
    },
    {
        "title": "On-topic and in-domain",
        "detail": "The visual belongs to the post's field/industry and speaks to its role-based audience.",
    },
    {
        "title": "Premium and professional",
        "detail": "Suitable for a LinkedIn feed: clean composition, tasteful lighting, no clutter.",
    },
    {
        "title": "No logos or watermarks",
        "detail": "No third-party logos, signatures, watermarks, or brand marks.",
    },
    {
        "title": "Correct on-image text only",
        "detail": "Any words rendered in the image must be on-topic, correctly spelled and in the post's language; avoid text-heavy images and distorted lettering.",
    },
    {
        "title": "No sensitive imagery",
        "detail": "No gore, nudity, drugs, weapons or content that would breach LinkedIn's policies.",
    },
]


DISCLAIMER = (
    "PostCraft generates and publishes content in line with LinkedIn's "
    "Professional Community Policies and posting guidelines. It does not "
    "produce spam, engagement bait, fabricated claims or prohibited content, "
    "and every post requires explicit human approval before it is published."
)


def guidelines_payload() -> Dict[str, Any]:
    """Grouped guidelines for `GET /api/guidelines`."""
    return {
        "disclaimer": DISCLAIMER,
        "groups": [
            {"id": "text", "title": "Post text", "items": TEXT_GUIDELINES},
            {"id": "image", "title": "Post image", "items": IMAGE_GUIDELINES},
            {"id": "safety", "title": "Safety & professionalism", "items": SAFETY_GUIDELINES},
        ],
        "source": "LinkedIn Professional Community Policies + LinkedIn feed best practice",
    }


def _render(items: List[Guideline]) -> str:
    return "\n".join(f"- {g['title']}: {g['detail']}" for g in items)


def text_rules_text() -> str:
    """Prompt block: LinkedIn rules for the post TEXT (incl. safety)."""
    return _render(TEXT_GUIDELINES + SAFETY_GUIDELINES)


def image_rules_text() -> str:
    """Prompt block: LinkedIn rules for the post IMAGE."""
    return _render(IMAGE_GUIDELINES)


__all__ = [
    "TEXT_GUIDELINES",
    "IMAGE_GUIDELINES",
    "SAFETY_GUIDELINES",
    "DISCLAIMER",
    "guidelines_payload",
    "text_rules_text",
    "image_rules_text",
]
