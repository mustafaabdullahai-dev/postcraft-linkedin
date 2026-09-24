"""Pydantic schemas for AI structured output and API contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Status enums ─────────────────────────────────────────────
class GenerationStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    GENERATED = "GENERATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    EDITED = "EDITED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalStatus(str, Enum):
    NOT_APPROVED = "NOT_APPROVED"
    APPROVED = "APPROVED"


class ValidationStatus(str, Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"


class PostPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class PostType(str, Enum):
    HOW_TO = "How-To"
    THOUGHT_LEADERSHIP = "Thought Leadership"
    INSIGHTS = "Insights"
    NEWS = "News"
    MOTIVATIONAL = "Motivational"
    PROMOTIONAL = "Promotional"


# ─── LLM structured outputs ───────────────────────────────────
class TopicAnalysis(BaseModel):
    topic: str
    category: str
    industry: str = Field(default="", description="Business field / industry / community the query belongs to")
    audience: str
    audience_roles: List[str] = Field(
        default_factory=list,
        description="2-4 specific role titles/segments worldwide that this post targets",
    )
    author_role: str = Field(
        default="",
        description="The 5-10y experience persona (role title + years of practice) who writes the post",
    )
    content_angle: str
    tone: str
    intent: str
    key_concepts: List[str] = Field(default_factory=list)


class ContentPlan(BaseModel):
    hook_angle: str
    structure: List[str]
    talking_points: List[str]
    cta_angle: str
    estimated_length: str = "800-1100 chars"
    # Filtering dimensions: what kind of post this is & how it should rank.
    priority: PostPriority = PostPriority.MEDIUM
    post_type: PostType = PostType.INSIGHTS


class LinkedInPostOutput(BaseModel):
    hook: str
    body: str
    cta: str
    hashtags: List[str] = Field(default_factory=list)
    full_post: str


class HashtagOutput(BaseModel):
    hashtags: List[str]

    @field_validator("hashtags")
    @classmethod
    def _normalize(cls, v: List[str]) -> List[str]:
        out: List[str] = []
        for h in v:
            h = h.strip()
            if not h:
                continue
            if not h.startswith("#"):
                h = "#" + h
            if h not in out:
                out.append(h)
        return out


class ImagePromptOutput(BaseModel):
    image_prompt: str
    visual_style: str
    composition: str
    negative_prompt: str


class ValidationOutput(BaseModel):
    valid: bool
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class SuggestOutput(BaseModel):
    improved: str
    note: str


class PostEditSuggestions(BaseModel):
    summary: str
    notes: List[str] = Field(default_factory=list)
    improved_draft: str


class ReworkOutput(BaseModel):
    """Formatter output: the draft rewritten to match the user's formatting
    choices (emojis / bullets / bold / structure). Content & voice preserved."""
    text: str


class FormattingPrefs(BaseModel):
    """User-selected formatting/style toggles for generation."""
    emojis: bool = True
    bullets: bool = True
    bold_keywords: bool = True
    short_paragraphs: bool = True
    practitioner_story: bool = False
    discussion_cta: bool = True
    # Target post length in words (hook + body + CTA, hashtags excluded).
    # 0 = auto (default length, let the LLM follow the plan).
    word_target: int = Field(default=0, ge=0, le=1500)


# ─── API contracts ────────────────────────────────────────────
class SuggestRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class SuggestResponse(BaseModel):
    original: str
    improved: str
    note: str


class GenerateRequest(BaseModel):
    user_query: str = Field(min_length=3, max_length=1000)
    regenerate_image: bool = False
    priority: Optional[str] = None
    post_type: Optional[str] = None
    # Language for the post text AND for any text shown in the generated image.
    # Free-form so the platform supports every language, not just a fixed list.
    language: str = Field(default="English", min_length=2, max_length=40)
    # Formatting/style toggles chosen in the UI.
    formatting: FormattingPrefs = Field(default_factory=FormattingPrefs)


class ReworkRequest(BaseModel):
    """Regenerate a post applying the suggestion draft + formatting choices."""
    text: str = Field(min_length=50)
    formatting: FormattingPrefs = Field(default_factory=FormattingPrefs)


class UpdatePostRequest(BaseModel):
    final_post: str = Field(min_length=1)
    hashtags: Optional[List[str]] = None


class ApprovalRequest(BaseModel):
    approved: bool = True


class PublishRequest(BaseModel):
    approved: bool = True


class RegenerateRequest(BaseModel):
    user_query: Optional[str] = None
    regenerate_image: bool = False


class RecordStatusCounts(BaseModel):
    total: int = 0
    ready_for_review: int = 0
    published: int = 0
    failed: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
    text_provider: str
    image_provider: str
    linkedin_mode: str
    sheets_mode: str
    linkedin_configured: bool = False
    time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


__all__ = [n for n in dir() if not n.startswith("_")]