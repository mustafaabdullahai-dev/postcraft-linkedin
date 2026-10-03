"""Text model provider abstraction (LangChain-backed + offline mock)."""
from __future__ import annotations

import asyncio
import json
import re
import string
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# A provider that emits unusable structured output is retried before giving up:
# the failure is a per-request coin flip, not a bad prompt or schema.
STRUCTURED_ATTEMPTS = 3
STRUCTURED_RETRY_BACKOFF_S = 0.6

# Rate limits are retried separately from the structured-output loop above.
# Groq's free tier caps the whole org at ~8k tokens/min, while one generate
# pipeline spends ~12k across six sequential calls, so a perfectly healthy
# request can 429 on the fifth node. The provider usually reports how long to
# wait ("Please try again in 3.05s"), so honour that when present.
RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_BACKOFF_S = 2.0
RATE_LIMIT_BACKOFF_MAX_S = 30.0

_JSON_DELIMITERS = ",}]:"


def _retry_after_seconds(exc: BaseException) -> Optional[float]:
    """Pull the provider's own retry hint out of a rate-limit error."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers:
        for key in ("retry-after", "x-ratelimit-reset-requests", "retry-after-ms"):
            raw = headers.get(key)
            if not raw:
                continue
            try:
                seconds = float(raw)
            except (TypeError, ValueError):
                continue
            # `retry-after-ms` and reset headers are sometimes milliseconds.
            if key.endswith("-ms") or seconds > RATE_LIMIT_BACKOFF_MAX_S * 1000:
                seconds /= 1000
            return max(0.0, min(seconds, RATE_LIMIT_BACKOFF_MAX_S))
    match = re.search(r"try again in ([\d.]+)\s*s", str(exc), re.IGNORECASE)
    if match:
        return max(0.0, min(float(match.group(1)), RATE_LIMIT_BACKOFF_MAX_S))
    return None


def _is_rate_limit_error(exc: BaseException) -> bool:
    if type(exc).__name__ in {"RateLimitError", "TooManyRequests"}:
        return True
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text and "rate limit" in text


async def _with_rate_limit_retry(operation: Callable[[], Any], label: str) -> Any:
    """Await `operation()`, retrying provider rate limits with backoff.

    The backend's own per-IP limiter cannot help here: the 429 comes from the
    upstream model provider and is billed to the whole organisation, so it must
    be absorbed by waiting rather than by shedding load.
    """
    delay = RATE_LIMIT_BACKOFF_S
    for attempt in range(1, RATE_LIMIT_ATTEMPTS + 1):
        try:
            return await operation()
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == RATE_LIMIT_ATTEMPTS:
                raise
            wait = _retry_after_seconds(exc)
            if wait is None:
                wait = min(delay, RATE_LIMIT_BACKOFF_MAX_S)
                delay *= 2
            logger.warning(
                "provider rate limited, backing off",
                call=label,
                attempt=attempt,
                attempts=RATE_LIMIT_ATTEMPTS,
                wait_s=round(wait, 2),
            )
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")


class _SafeFormatter(string.Formatter):
    """Fills known {placeholders}, leaves unknown ones untouched so literal
    braces can never crash formatting or leak into the prompt."""

    def get_field(self, field_name: str, args: tuple, kwargs: Dict[str, Any]):
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, IndexError):
            return "{" + field_name + "}", field_name


def _fill(template: str, variables: Dict[str, Any]) -> str:
    if not variables or "{" not in template:
        return template
    return _SafeFormatter().format(template, **variables)


def repair_unescaped_quotes(raw: str) -> Optional[str]:
    """Re-escape straight double quotes a provider emitted bare inside a JSON
    string value, returning valid JSON or None if it cannot be repaired.

    DeepSeek sometimes copies quotes out of the source post into tool-call
    arguments without escaping them:

        {"notes": ["... 'Most "our RAG is broken" tickets' ..."]}

    The early-closing quote truncates the string, so the whole payload fails to
    parse and the call is discarded. A quote can only legitimately close a
    string when the next meaningful character is a JSON delimiter (`,` `}` `]`
    `:`); anything else means the quote was part of the text.
    """
    if not isinstance(raw, str) or not raw:
        return None
    try:
        json.loads(raw)
        return None  # already valid — nothing to repair
    except ValueError:
        pass

    out: List[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
            continue
        if escaped:
            out.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            i += 1
            continue
        if ch == '"':
            j = i + 1
            while j < len(raw) and raw[j] in " \t\r\n":
                j += 1
            if j < len(raw) and raw[j] in _JSON_DELIMITERS:
                in_string = False
                out.append(ch)
            else:
                out.append('\\"')
            i += 1
            continue
        out.append(ch)
        i += 1

    candidate = "".join(out)
    try:
        json.loads(candidate)
    except ValueError:
        return None
    return candidate


def _recover_structured(raw: Any, schema: Type[T]) -> Optional[T]:
    """Salvage a tool call the provider emitted with unparseable arguments.

    Returns None when nothing usable can be recovered, so the caller retries.
    The repaired payload is validated against `schema`, so a wrong guess can
    never leak into the app — it either validates or is discarded.
    """
    if raw is None:
        return None
    for call in getattr(raw, "invalid_tool_calls", None) or []:
        args = call.get("args") if isinstance(call, dict) else None
        if not isinstance(args, str):
            continue
        for candidate in (repair_unescaped_quotes(args), args):
            if not candidate:
                continue
            try:
                return schema.model_validate(json.loads(candidate))
            except Exception:  # noqa: BLE001 - try the next candidate
                continue
    return None

BANNED_CLICHES = [
    "in today's rapidly evolving world",
    "game-changer",
    "delve",
    "unleash",
    "revolutionize",
    "it's important to note",
    "ever-evolving landscape",
]


class TextModelProvider(ABC):
    """Interface so the text backend can be swapped (OpenAI/Qwen/Anthropic/Mock)."""

    name: str = "base"

    @abstractmethod
    async def structured(
        self,
        schema: Type[T],
        system: str,
        human: str,
        **variables: Any,
    ) -> T:
        """Run a chat completion and parse it into `schema`."""

    @abstractmethod
    async def complete(self, system: str, human: str) -> str:
        """Run a plain chat completion."""


# ─── LangChain implementation ─────────────────────────────────
class LangChainTextProvider(TextModelProvider):
    def __init__(self, model: Any, name: str, structured_method: str = "function_calling"):
        self._model = model
        self.name = name
        self._structured_method = structured_method

    def _structured_chain(self, schema: Type[T]):
        # include_raw turns a parse failure into a returned dict instead of a
        # raised exception, which is what makes the retry loop below possible.
        return self._model.with_structured_output(
            schema, method=self._structured_method, include_raw=True
        )

    async def structured(
        self, schema: Type[T], system: str, human: str, **variables: Any
    ) -> T:
        # NOTE: system/human strings may contain {placeholders}. We pass them
        # as raw message content (NOT as template values) to avoid double
        # interpolation leaking literal {topic} into the model.
        from langchain_core.messages import HumanMessage, SystemMessage

        human_text = _fill(human, variables) if variables else human
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=human_text),
        ]
        chain = self._structured_chain(schema)

        for attempt in range(1, STRUCTURED_ATTEMPTS + 1):
            outcome = await _with_rate_limit_retry(
                lambda: chain.ainvoke(messages), f"structured:{schema.__name__}"
            )
            parsed = outcome.get("parsed")
            if isinstance(parsed, schema):
                return parsed
            if isinstance(parsed, dict):
                return schema.model_validate(parsed)

            recovered = _recover_structured(outcome.get("raw"), schema)
            if recovered is not None:
                logger.info(
                    "structured output repaired from invalid tool call",
                    schema=schema.__name__,
                    attempt=attempt,
                )
                return recovered

            logger.warning(
                "structured output unusable, retrying",
                schema=schema.__name__,
                attempt=attempt,
                attempts=STRUCTURED_ATTEMPTS,
                error=str(outcome.get("parsing_error"))[:200],
            )
            if attempt < STRUCTURED_ATTEMPTS:
                await asyncio.sleep(STRUCTURED_RETRY_BACKOFF_S * attempt)

        raise ValueError(
            f"{schema.__name__}: the model returned no usable structured output "
            f"after {STRUCTURED_ATTEMPTS} attempts."
        )

    async def complete(self, system: str, human: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [SystemMessage(content=system), HumanMessage(content=human)]
        msg = await _with_rate_limit_retry(
            lambda: self._model.ainvoke(messages), "complete"
        )
        return msg.content if hasattr(msg, "content") else str(msg)


# ─── Offline mock implementation ─────────────────────────────
HOOKS = [
    "Most teams don't fail at {topic} because the models are weak.",
    "The hard part of {topic} is never the demo — it's production.",
    "Engineers keep asking about {topic}. The real answer is architectural.",
]


class MockTextProvider(TextModelProvider):
    """Deterministic offline provider so the whole platform runs without keys."""

    name = "mock"

    async def complete(self, system: str, human: str) -> str:
        return f"[mock completion]\n{human[:400]}"

    async def structured(
        self, schema: Type[T], system: str, human: str, **variables: Any
    ) -> T:
        await asyncio.sleep(0.05)
        human = _fill(human, variables) if variables else human
        topic = variables.get("topic") or _extract(human, r"Topic:\s*(.+)") or _extract(
            human, r"User query:\s*(.+)"
        ) or "the topic"
        post = variables.get("post", "")
        cls_name = schema.__name__

        if cls_name == "TopicAnalysis":
            return schema.model_validate(
                {
                    "topic": topic.strip()[:200],
                    "category": "Industry Insights",
                    "industry": "Technology",
                    "audience": "Professionals and leaders who build and ship AI-enabled products",
                    "audience_roles": ["AI Engineers", "Engineering Managers", "Tech Leads"],
                    "author_role": "a Principal Software Engineer with 9 years of experience",
                    "content_angle": "Practical practitioner comparison",
                    "tone": "Experienced technical professional",
                    "intent": "Educational thought leadership",
                    "key_concepts": _key_concepts(topic),
                }
            )
        if cls_name == "ContentPlan":
            return schema.model_validate(
                {
                    "hook_angle": f"A concrete observation about {topic}",
                    "structure": [
                        "HOOK",
                        "PROBLEM",
                        "TECHNICAL INSIGHT",
                        "ENGINEERING PERSPECTIVE",
                        "TAKEAWAYS",
                        "CONCLUSION",
                        "CTA",
                    ],
                    "talking_points": [
                        f"Why {topic} matters in production systems",
                        "Where naive implementations break down",
                        "The architectural trade-off worth calling out",
                        "A pragmatic way to structure the solution",
                        "What to measure before shipping",
                    ],
                    "cta_angle": "Ask readers how they approach it in their stack",
                    "estimated_length": "800-1100 chars",
                    "priority": "Medium",
                    "post_type": "Insights",
                }
            )
        if cls_name == "LinkedInPostOutput":
            return schema.model_validate(self._post(topic))
        if cls_name == "HashtagOutput":
            tags = _dynamic_tags(topic, post)
            return schema.model_validate({"hashtags": tags[:9]})
        if cls_name == "ImagePromptOutput":
            return schema.model_validate(
                {
                    "image_prompt": (
                        f"A premium futuristic AI engineering visualization illustrating {topic}, "
                        "graph-based orchestration connecting intelligent agents, tools and memory, "
                        "professional software architecture aesthetic, dark technology environment, "
                        "cinematic lighting, clean composition, sophisticated enterprise AI visual, "
                        "no text, no watermark, suitable for a LinkedIn professional post"
                    ),
                    "visual_style": "Premium dark tech / enterprise AI",
                    "composition": "Central focal element with soft depth-of-field background",
                    "negative_prompt": (
                        "text, watermark, logo, low quality, distorted anatomy, "
                        "cluttered layout, cartoonish, irrelevant objects"
                    ),
                }
            )
        if cls_name == "ValidationOutput":
            issues: List[str] = []
            suggestions: List[str] = []
            low = post.lower()
            for cliche in BANNED_CLICHES:
                if cliche in low:
                    issues.append(f"Contains AI cliché: '{cliche}'")
            if len(post) < 300:
                issues.append("Post is too short for a LinkedIn engineering post")
            if len(post) > 3000:
                issues.append("Post exceeds recommended LinkedIn length")
            if not re.search(r"(thoughts|experience|approach|share|\?)", low):
                suggestions.append("Consider a more natural discussion CTA")
            score = max(0.5, 0.95 - 0.1 * len(issues))
            return schema.model_validate(
                {
                    "valid": not issues,
                    "quality_score": round(score, 2),
                    "issues": issues,
                    "suggestions": suggestions,
                }
            )
        if cls_name == "PostEditSuggestions":
            return schema.model_validate(
                {
                    "summary": "Sharpen the opening hook and give the CTA a concrete prompt.",
                    "notes": [
                        "Open with the contrast, not the topic statement.",
                        "Tighten the middle paragraph by cutting repeated ideas.",
                        "Make the CTA ask for the audience's real approach in their environment.",
                    ],
                    "improved_draft": post,
                }
            )
        if cls_name == "ReworkOutput":
            return schema.model_validate({"text": variables.get("draft") or post or "reworked"})
        raise ValueError(f"Mock provider has no generator for {cls_name}")

    def _post(self, topic: str) -> BaseModel:
        hook = HOOKS[0].format(topic=topic)
        body = (
            f"Teams treat {topic} as a model-selection problem.\n"
            "It is not. The model is usually the easy 20%.\n\n"
            "The engineering problem is everything around it: state, retries,\n"
            "observability, and a workflow you can actually reason about when\n"
            "step 4 of 9 fails at 2am.\n\n"
            "From an engineering perspective, the useful pattern is:\n\n"
            "• Make every step explicit and independently testable\n"
            "• Keep state typed so failures are debuggable, not silent\n"
            "• Design the human checkpoint before you design the automation\n\n"
            "The trade-off is speed vs. control. Demos reward speed;\n"
            "production rewards control.\n\n"
            "How is your team drawing that line right now?"
        )
        cta = "What's been your experience with this in production?"
        hashtags = _dynamic_tags(topic, "")
        full = f"{hook}\n\n{body}\n\n{cta}\n\n" + " ".join(hashtags)
        return {
            "hook": hook,
            "body": body,
            "cta": cta,
            "hashtags": hashtags,
            "full_post": full,
        }


def _extract(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _key_concepts(topic: str) -> List[str]:
    words = [w for w in re.findall(r"[A-Za-z]{3,}", topic)]
    base = ["workflow state", "structured output", "human-in-the-loop"]
    return (words[:4] + base)[:7]


def _dynamic_tags(topic: str, post: str = "") -> List[str]:
    """Deterministic, topic-derived hashtags (no fixed brand tags)."""
    seen: List[str] = []
    text = f"{topic} {post}"
    for kw in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text):
        if kw.lower() in {"and", "the", "for", "with", "how", "why", "what", "this"}:
            continue
        tag = "#" + kw[:1].upper() + kw[1:]
        if tag not in seen:
            seen.append(tag)
        if len(seen) >= 4:
            break
    base = ["#CareerGrowth", "#Leadership", "#Innovation", "#FutureOfWork"]
    out = seen + [b for b in base if b not in seen]
    return out[:9]


# ─── Provider factory ─────────────────────────────────────────
def get_text_provider(settings: Settings) -> TextModelProvider:
    choice = (settings.text_provider or "auto").lower()

    def openai_provider() -> Optional[LangChainTextProvider]:
        if not settings.openai_api_key:
            return None
        from langchain_openai import ChatOpenAI

        return LangChainTextProvider(
            ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model,
                       temperature=0.6),
            name=f"openai:{settings.openai_model}",
        )

    def anthropic_provider() -> Optional[LangChainTextProvider]:
        if not settings.anthropic_api_key:
            return None
        from langchain_anthropic import ChatAnthropic

        return LangChainTextProvider(
            ChatAnthropic(api_key=settings.anthropic_api_key,
                          model=settings.anthropic_model, temperature=0.6),
            name=f"anthropic:{settings.anthropic_model}",
        )

    def qwen_provider() -> Optional[LangChainTextProvider]:
        if not settings.qwen_api_key:
            return None
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {
            "api_key": settings.qwen_api_key,
            "base_url": settings.qwen_base_url,
            "model": settings.qwen_text_model,
            "temperature": 0.6,
        }
        if settings.qwen_enable_thinking:
            # Deep-thinking models (e.g. qwen3.7-plus) expose reasoning via
            # this OpenAI-compatible extension header.
            kwargs["extra_body"] = {"enable_thinking": True}

        return LangChainTextProvider(
            ChatOpenAI(**kwargs),
            name=f"qwen:{settings.qwen_text_model}",
            structured_method=settings.structured_output_method,
        )

    def groq_provider() -> Optional[LangChainTextProvider]:
        if not settings.groq_api_key:
            return None
        from langchain_openai import ChatOpenAI

        return LangChainTextProvider(
            ChatOpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
                model=settings.groq_model,
                temperature=0.6,
                model_kwargs={"max_completion_tokens": int(settings.groq_max_completion_tokens)},
                # Groq's free tier is capped at ~8k tokens/min for the whole org
                # (identical for 120b/20b/qwen3.8), and the pipeline makes several
                # calls in a row. Requesting 8192 per call instantly exhausts the
                # budget and returns 429, so cap it well under the limit: posts
                # target 700-1300 chars and gpt-oss reasoning needs a few hundred
                # tokens, so 3072 is comfortable headroom.
            ),
            name=f"groq:{settings.groq_model}",
            structured_method=settings.structured_output_method,
        )

    def openrouter_provider() -> Optional[LangChainTextProvider]:
        if not settings.openrouter_api_key:
            return None
        from langchain_openai import ChatOpenAI

        return LangChainTextProvider(
            ChatOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
                temperature=0.6,
                default_headers={
                    # OpenRouter attribution headers identify the app that calls the API.
                    "HTTP-Referer": settings.frontend_url,
                    "X-Title": settings.app_name,
                },
            ),
            name=f"openrouter:{settings.openrouter_model}",
            structured_method=(
                settings.openrouter_structured_output_method
                or settings.structured_output_method
            ),
        )

    def deepseek_provider() -> Optional[LangChainTextProvider]:
        if not settings.deepseek_api_key:
            return None
        from langchain_openai import ChatOpenAI

        return LangChainTextProvider(
            ChatOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                temperature=0.6,
            ),
            name=f"deepseek:{settings.deepseek_model}",
            structured_method=(
                settings.deepseek_structured_output_method
                or settings.structured_output_method
            ),
        )

    factories: Dict[str, Callable[[], Optional[TextModelProvider]]] = {
        "openai": openai_provider,
        "anthropic": anthropic_provider,
        "qwen": qwen_provider,
        "groq": groq_provider,
        "openrouter": openrouter_provider,
        "deepseek": deepseek_provider,
    }

    if choice == "mock":
        logger.info("text_provider selected", provider="mock")
        return MockTextProvider()

    if choice in factories:
        provider = factories[choice]()
        if provider is None:
            logger.warning("text provider configured but key missing", provider=choice)
            return MockTextProvider()
        logger.info("text_provider selected", provider=provider.name)
        return provider

    # openrouter needs the key; groq/openai/qwen/anthropic stay for backwards compat.
    # deepseek sits after groq so existing auto-mode precedence is unchanged.
    for key in ("openrouter", "groq", "deepseek", "openai", "qwen", "anthropic"):
        provider = factories[key]()
        if provider is not None:
            logger.info("text_provider selected (auto)", provider=provider.name)
            return provider

    logger.info("text_provider selected (auto)", provider="mock (no keys found)")
    return MockTextProvider()


__all__ = [
    "TextModelProvider",
    "LangChainTextProvider",
    "MockTextProvider",
    "get_text_provider",
]