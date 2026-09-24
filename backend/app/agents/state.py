"""LangGraph workflow state for the LinkedIn content agent."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class LinkedInPostState(TypedDict, total=False):
    user_query: str

    topic: str
    category: str
    industry: str
    audience: str
    audience_roles: List[str]
    author_role: str
    key_concepts: List[str]
    content_angle: str
    priority: str
    post_type: str
    language: str  # chosen language for post text + any text in the image
    formatting: dict  # FormattingPrefs.dump() — emojis/bullets/bold/... toggles
    content_plan: dict  # serialized ContentPlan

    generated_post: str
    hashtags: List[str]

    image_prompt: str
    image_url: Optional[str]
    image_negative_prompt: str
    image_provider: str

    validation_result: Dict[str, Any]
    validation_status: str

    review_status: str
    user_approved: Optional[bool]
    edited_post: Optional[str]

    text_model: str

    linkedin_post_id: Optional[str]
    publishing_status: str
    publish_error: Optional[str]

    google_sheet_status: str

    error: Optional[str]

    record_id: str

    # Multi-user support: who owns this thread + their LinkedIn credentials.
    owner_id: str
    linkedin_user: Dict[str, Any]

    created_at: str
    updated_at: str