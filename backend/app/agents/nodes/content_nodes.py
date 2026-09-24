"""LangGraph workflow nodes — each node calls the providers directly."""
from __future__ import annotations

import re
from typing import Any, Dict

from app.agents.state import LinkedInPostState
from app.core.logging import get_logger
from app.models.schemas import (
    ContentPlan,
    HashtagOutput,
    ImagePromptOutput,
    LinkedInPostOutput,
    PostPriority,
    PostType,
    ReworkOutput,
    TopicAnalysis,
    ValidationOutput,
)
from app.prompts import content as content_prompts
from app.prompts import image as image_prompts
from app.prompts import topic_analysis as topic_prompts

logger = get_logger(__name__)


def _is_tag_line(line: str) -> bool:
    tokens = line.strip().split()
    if not tokens:
        return False
    return all(t.startswith("#") for t in tokens)


def _is_hashtags_label(line: str) -> bool:
    return bool(re.fullmatch(r"#?\s*hashtags:?\s*", line.strip(), re.IGNORECASE))


def _strip_label(line: str) -> str:
    """If a line starts with 'Hashtags:' or 'hashtags :', return the rest."""
    m = re.match(r"^\s*#?\s*hashtags:?\s*:\s*(.*)$", line.strip(), re.IGNORECASE)
    if m:
        return m.group(1)
    return line


def clean_post(text: str, hashtags) -> str:
    """Normalize a generated post:
    - drop any 'Hashtags:' label lines and any tag-only lines anywhere,
      then append ONE clean hashtag line from the authoritative hashtags field.
    This removes duplicated/extra hashtag blocks raised by the validator while
    preserving inline hashtags inside sentences."""
    cleaned: list[str] = []
    for raw in text.split("\n"):
        line = _strip_label(raw).strip()
        if _is_hashtags_label(raw) or _is_tag_line(line):
            continue
        cleaned.append(raw.rstrip())

    body = "\n".join(cleaned).strip()
    tags = " ".join(h for h in hashtags if h.startswith("#"))
    if tags:
        body = f"{body}\n\n{tags}"
    return body


class NodeContext:
    """Injected into every node: providers + shared services."""

    def __init__(
        self,
        text_provider=None,
        image_provider=None,
        linkedin_publisher=None,
        sheets_service=None,
        store=None,
        user_store=None,
        settings=None,
    ):
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.linkedin_publisher = linkedin_publisher
        self.sheets_service = sheets_service
        self.store = store
        self.user_store = user_store
        self.settings = settings


DEFAULT_FORMATTING = {
    "emojis": True,
    "bullets": True,
    "bold_keywords": True,
    "short_paragraphs": True,
    "practitioner_story": False,
    "discussion_cta": True,
    "word_target": 0,
}


def formatting_directives(prefs) -> str:
    """Render the user's formatting toggles as explicit instructions for the LLM."""
    prefs = prefs if isinstance(prefs, dict) and prefs else DEFAULT_FORMATTING

    def on(key: str, default: bool) -> bool:
        return bool(prefs.get(key, default))
    word_target = prefs.get("word_target") or 0
    length_row = (
        f"Target length: exactly ~{int(word_target)} words (hook + body + CTA, hashtags excluded; "
        "stay within ±15%)"
        if word_target
        else "Target length: auto (follow the plan's estimated_length)"
    )
    rows = [
        ("Length", length_row),
        ("Emojis", "MUST include 3-7 emojis in EVERY post type" if on("emojis", True) else "NO emojis anywhere"),
        ("Bullets", "use • bullet lines for lists/takeaways when useful" if on("bullets", True) else "NO bullet lists; flowing prose only"),
        ("Bold keywords", "**bold** the few most important terms per section" if on("bold_keywords", True) else "NO **bold** text"),
        ("Paragraphs", "short scannable paragraphs (1-3 sentences)" if on("short_paragraphs", True) else "normal-length paragraphs"),
        ("Practitioner story", "include a real-feeling practitioner perspective/example" if on("practitioner_story", False) else "practitioner insight without personal-story framing"),
        ("CTA", "end with a discussion CTA asking the audience a context-rich question" if on("discussion_cta", True) else "end with a concise takeaway close, no question"),
    ]
    return "\n".join(f"- {name}: {value}" for name, value in rows)


async def analyze_topic(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    result: TopicAnalysis = await ctx.text_provider.structured(
        TopicAnalysis,
        topic_prompts.TOPIC_ANALYSIS_SYSTEM,
        topic_prompts.TOPIC_ANALYSIS_HUMAN,
        user_query=state["user_query"],
    )
    return {
        "topic": result.topic,
        "category": result.category,
        "industry": result.industry,
        "audience": result.audience,
        "audience_roles": result.audience_roles,
        "author_role": result.author_role,
        "content_angle": result.content_angle,
        "key_concepts": result.key_concepts,
    }


async def plan_content(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    preferred_priority = state.get("priority", "")
    preferred_post_type = state.get("post_type", "")
    result: ContentPlan = await ctx.text_provider.structured(
        ContentPlan,
        content_prompts.PLAN_SYSTEM,
        content_prompts.PLAN_HUMAN,
        topic=state.get("topic", ""),
        industry=state.get("industry", "") or state.get("category", ""),
        category=state.get("category", ""),
        audience=state.get("audience", ""),
        audience_roles=", ".join(state.get("audience_roles") or []),
        content_angle=state.get("content_angle", ""),
        key_concepts=state.get("key_concepts", []),
        preferred_priority=preferred_priority or "none (let you decide)",
        preferred_post_type=preferred_post_type or "none (let you decide)",
        user_query=state["user_query"],
        language=state.get("language", "English"),
        formatting=formatting_directives(state.get("formatting")),
    )
    # The UI filters are a hard constraint; only fall back to the model's pick
    # when the filter value isn't one of the known enums.
    priority = (
        preferred_priority
        if preferred_priority in {p.value for p in PostPriority}
        else result.priority.value
    )
    post_type = (
        preferred_post_type
        if preferred_post_type in {t.value for t in PostType}
        else result.post_type.value
    )
    return {
        "content_plan": result.model_dump(),
        "priority": priority,
        "post_type": post_type,
    }


async def generate_linkedin_post(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    plan = state.get("content_plan") or {}
    result: LinkedInPostOutput = await ctx.text_provider.structured(
        LinkedInPostOutput,
        content_prompts.WRITER_SYSTEM,
        content_prompts.WRITER_HUMAN,
        topic=state.get("topic", ""),
        industry=state.get("industry", ""),
        audience=state.get("audience", ""),
        audience_roles=", ".join(state.get("audience_roles") or []),
        author_role=state.get("author_role") or "a seasoned professional",
        content_angle=state.get("content_angle", ""),
        plan={k: v for k, v in plan.items() if k != "talking_points"},
        talking_points="\n".join(f"- {p}" for p in plan.get("talking_points", [])),
        user_experience="",
        user_query=state["user_query"],
        language=state.get("language", "English"),
        formatting=formatting_directives(state.get("formatting")),
    )
    return {
        "generated_post": clean_post(result.full_post, result.hashtags),
        "hashtags": result.hashtags,
        "language": state.get("language", "English"),
        "text_model": ctx.text_provider.name,
    }


async def generate_hashtags(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    result: HashtagOutput = await ctx.text_provider.structured(
        HashtagOutput,
        image_prompts.HASHTAG_SYSTEM,
        image_prompts.HASHTAG_HUMAN,
        topic=state.get("topic", ""),
        industry=state.get("industry", ""),
        audience=state.get("audience", ""),
        post=state.get("generated_post", ""),
        language=state.get("language", "English"),
    )
    tags = result.hashtags or []
    return {"hashtags": tags[:10]}


async def generate_image_prompt(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    result: ImagePromptOutput = await ctx.text_provider.structured(
        ImagePromptOutput,
        image_prompts.IMAGE_PROMPT_SYSTEM,
        image_prompts.IMAGE_PROMPT_HUMAN,
        topic=state.get("topic", ""),
        industry=state.get("industry", ""),
        audience=state.get("audience", ""),
        audience_roles=", ".join(state.get("audience_roles") or []),
        content_angle=state.get("content_angle", ""),
        key_concepts=state.get("key_concepts", []),
        user_query=state["user_query"],
        language=state.get("language", "English"),
    )
    return {
        "image_prompt": result.image_prompt,
        "image_negative_prompt": result.negative_prompt,
    }


async def rework_post(
    ctx: NodeContext,
    *,
    topic: str,
    audience: str,
    language: str,
    draft: str,
    formatting: dict,
    user_query: str,
) -> Dict[str, Any]:
    """Rewrite an existing draft to apply the user's formatting toggles (used
    right after edit suggestions): LLM formatting pass + fresh hashtags +
    deterministic re-validation."""
    formatter = await ctx.text_provider.structured(
        ReworkOutput,
        content_prompts.REWORK_SYSTEM,
        content_prompts.REWORK_HUMAN,
        topic=topic,
        audience=audience,
        language=language,
        user_query=user_query,
        formatting=formatting_directives(formatting),
        draft=draft,
    )
    body = (formatter.text or "").strip() or draft
    working = {
        "user_query": user_query,
        "topic": topic,
        "industry": "",
        "audience": audience,
        "generated_post": body,
        "language": language,
    }
    hashtag_state = await generate_hashtags(working, ctx)
    working["hashtags"] = hashtag_state["hashtags"]
    validation_state = await validate_content(working, ctx)
    return {
        "generated_post": body,
        "hashtags": hashtag_state["hashtags"],
        "validation_result": validation_state["validation_result"],
        "validation_status": validation_state["validation_status"],
        "language": language,
        "text_model": ctx.text_provider.name,
    }


async def generate_image(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    prompt = state.get("image_prompt", "") or state.get("topic", "")
    logger.info("generating image", provider=getattr(ctx.image_provider, "name", "?"))
    result = await ctx.image_provider.generate_image(prompt)
    return {
        "image_url": result.image_url,
        "image_provider": result.provider,
    }


async def validate_content(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    from app.services.validator import ContentValidator

    validator = ContentValidator(ctx.text_provider)
    result: ValidationOutput = await validator.validate(
        post=state.get("generated_post", ""),
        hashtags=state.get("hashtags", []),
        user_query=state["user_query"],
    )
    status = "VALID" if result.valid else "INVALID"
    if not result.valid:
        logger.warning("content validation rejected", issues=result.issues)
    return {
        "validation_result": result.model_dump(),
        "validation_status": status,
    }


async def human_review(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    from langgraph.types import interrupt

    approved: bool = interrupt(
        {
            "question": "Approve this LinkedIn post?",
            "status": "READY_FOR_REVIEW",
        }
    )
    logger.info("human review decided", approved=approved)
    return {
        "user_approved": approved,
        "review_status": "APPROVED" if approved else "REJECTED",
    }


async def publish_to_linkedin(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    if not state.get("user_approved"):
        raise PermissionError("Post must be manually approved before publishing.")

    text = state.get("edited_post") or state.get("generated_post", "")
    linkedin_user = state.get("linkedin_user") or {}
    access_token = linkedin_user.get("access_token", "") if isinstance(linkedin_user, dict) else ""
    person_urn = linkedin_user.get("urn", "") if isinstance(linkedin_user, dict) else ""

    # Prefer the LIVE user record so a refreshed/rotated token is always used;
    # refresh happens transparently and is persisted back to the store.
    owner_id = state.get("owner_id", "")
    live_user = ctx.user_store.get(owner_id) if ctx and ctx.user_store else None
    if live_user and live_user.urn:
        refresh = getattr(ctx.linkedin_publisher, "ensure_valid_access_token", None)
        if refresh is None:
            access_token, person_urn = live_user.access_token, live_user.urn
        else:
            try:
                access_token = await refresh(live_user, ctx.user_store)
                person_urn = live_user.urn
            except Exception as exc:  # noqa: BLE001
                logger.warning("linkedin token refresh failed; using stored token", error=str(exc))

    try:
        result = await ctx.linkedin_publisher.publish_text_post(
            text=text,
            image_url=state.get("image_url"),
            hashtags=state.get("hashtags", []),
            access_token=access_token,
            person_urn=person_urn,
        )
        return {
            "linkedin_post_id": result.get("post_id"),
            "publishing_status": result.get("status", "PUBLISHED"),
            "publish_error": result.get("error"),
        }
    except Exception as exc:  # noqa: BLE001 - keep the post, mark failure
        logger.error("linkedin publish failed", error=str(exc))
        return {
            "linkedin_post_id": None,
            "publishing_status": "FAILED",
            "publish_error": str(exc),
        }


async def save_to_google_sheets(state: LinkedInPostState, ctx: NodeContext = None) -> Dict[str, Any]:
    try:
        record_payload = {
            "record_id": state.get("record_id", ""),
            "owner_id": state.get("owner_id", ""),
            "user_query": state.get("user_query", ""),
            "priority": state.get("priority", ""),
            "post_type": state.get("post_type", ""),
            "topic": state.get("topic", ""),
            "audience": state.get("audience", ""),
            "content_angle": state.get("content_angle", ""),
            "generated_post": state.get("generated_post", ""),
            "final_post": state.get("edited_post") or state.get("generated_post", ""),
            "hashtags": state.get("hashtags", []),
            "image_prompt": state.get("image_prompt", ""),
            "image_url": state.get("image_url"),
            "text_model": state.get("text_model", ""),
            "image_provider": state.get("image_provider", ""),
            "validation_status": state.get("validation_status", ""),
            "review_status": state.get("review_status", ""),
            "approval_status": "APPROVED" if state.get("user_approved") else "NOT_APPROVED",
            "publishing_status": state.get("publishing_status", ""),
            "linkedin_post_id": state.get("linkedin_post_id"),
            "error": state.get("error"),
        }
        status = await ctx.sheets_service.append_record(
            record_payload, state_id=state.get("record_id")
        )
        return {"google_sheet_status": status}
    except Exception as exc:  # noqa: BLE001
        logger.error("google sheets log failed", error=str(exc))
        return {"google_sheet_status": "FAILED"}


__all__ = [
    "NodeContext",
    "analyze_topic",
    "plan_content",
    "generate_linkedin_post",
    "generate_hashtags",
    "generate_image_prompt",
    "generate_image",
    "validate_content",
    "human_review",
    "publish_to_linkedin",
    "save_to_google_sheets",
    "rework_post",
    "formatting_directives",
]