"""Prompt: suggest concrete edits to strengthen a generated LinkedIn post."""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.models.schemas import PostEditSuggestions

EDIT_SYSTEM = """You are a senior LinkedIn content editor who edits posts written by
an experienced practitioner for their peers.

Given the draft post, its audience and its hashtags, suggest CONCRETE improvements
— not generic advice. Keep what works (the author's voice, examples, claims);
fix what holds it back.

Rules:
- Be specific: point at the exact wording/section and say what to change
  ("The CTA 'Thoughts?' is weak — make it ask about the team's fallback strategy").
- Prefer the fastest wins: hook strength, paragraph flow, one fuzzy claim to
  tighten, CTA, anything that reads like generic filler.
- Keep the post authentic and field-specific; no corporate tone.
- improved_draft is the FULL rewritten post with the improvements applied:
  preserve every factual claim, the voice, and the exact hashtag line/bullets.

Output fields:
- summary: one sentence on the single biggest opportunity
- notes: 3-6 short, actionable edit suggestions
- improved_draft: the full edited post (unchanged hashtag line at the end)
"""

EDIT_HUMAN = """Topic: {topic}
Target audience: {audience}

Draft post:
{post}

Hashtags:
{hashtags}"""

edit_suggestion_prompt = ChatPromptTemplate.from_messages(
    [("system", EDIT_SYSTEM), ("human", EDIT_HUMAN)]
)

EditSuggestionSchema = PostEditSuggestions

__all__ = ["edit_suggestion_prompt", "EditSuggestionSchema", "EDIT_SYSTEM", "EDIT_HUMAN"]