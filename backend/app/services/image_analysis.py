"""LLM review of an uploaded image against LinkedIn's image guidelines.

Runs one vision call through an OpenAI-compatible endpoint — Qwen-VL on
DashScope, or Gemini's OpenAI-compatible shim — and returns a PASSED/REVIEW
verdict with the specific issues found.

Failures are never fatal: if no vision provider is configured or the call
errors, the upload still succeeds with an UNVERIFIED status.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.prompts.guidelines import image_rules_text

logger = get_logger(__name__)

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_QWEN_VL_MODEL = "qwen-vl-max"
DEFAULT_GEMINI_VL_MODEL = "gemini-2.5-flash"

_SYSTEM = (
    """You review ONE image that a user wants to publish with a LinkedIn post.
Judge it strictly against LinkedIn's image guidelines and reply with ONLY a
JSON object (no prose, no markdown):

{"status": "PASSED" | "REVIEW", "score": 0.0-1.0, "issues": ["..."], "summary": "one sentence"}

LINKEDIN IMAGE GUIDELINES (authoritative):
"""
    + image_rules_text()
    + """

RULES:
- Use "PASSED" only when the image clearly satisfies every guideline.
- Use "REVIEW" when anything is questionable: off-topic for the post, logos,
  watermarks or brand marks, gibberish / misspelled / wrong-language text,
  unprofessional or low-quality look, or sensitive content.
- "issues": at most 4 short, concrete bullets (empty list when PASSED).
- Judge only what is visible; never invent problems.
"""
)


@dataclass
class ImageAnalysis:
    status: str  # PASSED | REVIEW | UNVERIFIED
    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    summary: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "issues": self.issues,
            "summary": self.summary,
            "model": self.model,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


def _candidates(settings: Settings) -> List[Tuple[str, str, str, str]]:
    """(name, api_key, base_url, model) in preference order."""
    prov = (settings.vision_provider or "auto").lower()
    if prov == "off":
        return []
    out: List[Tuple[str, str, str, str]] = []
    if prov in ("auto", "qwen") and settings.qwen_api_key:
        out.append(
            (
                "qwen",
                settings.qwen_api_key,
                settings.qwen_base_url.rstrip("/"),
                settings.vision_model or DEFAULT_QWEN_VL_MODEL,
            )
        )
    if prov in ("auto", "gemini") and settings.gemini_api_key:
        out.append(
            (
                "gemini",
                settings.gemini_api_key,
                GEMINI_OPENAI_BASE,
                settings.vision_model or DEFAULT_GEMINI_VL_MODEL,
            )
        )
    return out


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def _call_vision(
    name: str, api_key: str, base_url: str, model: str, data_uri: str, timeout: float = 45.0
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Review this image for a LinkedIn post."},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
    resp.raise_for_status()
    body = resp.json()
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):  # some providers return content parts
        content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    parsed = _extract_json(str(content))
    if not parsed:
        raise ValueError("vision model returned no parseable JSON")
    return parsed


async def analyze_image(data: bytes, settings: Settings, mime: str = "image/jpeg") -> ImageAnalysis:
    """Review uploaded image bytes against the LinkedIn image guidelines."""
    candidates = _candidates(settings)
    if not candidates:
        return ImageAnalysis(status="UNVERIFIED", summary="No vision provider configured.")

    data_uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    for name, api_key, base_url, model in candidates:
        try:
            parsed = await _call_vision(name, api_key, base_url, model, data_uri)
            status = str(parsed.get("status", "")).upper()
            status = "PASSED" if status == "PASSED" else "REVIEW"
            try:
                score = float(parsed.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            issues = [str(i)[:160] for i in parsed.get("issues") or []][:4]
            return ImageAnalysis(
                status=status,
                score=max(0.0, min(1.0, score)),
                issues=issues,
                summary=str(parsed.get("summary", ""))[:220],
                model=f"{name}:{model}",
            )
        except Exception as exc:  # noqa: BLE001 — try the next provider, never block the upload
            logger.warning("image analysis failed", provider=name, model=model, error=str(exc))
            continue

    return ImageAnalysis(status="UNVERIFIED", summary="Image could not be reviewed right now.")


__all__ = ["ImageAnalysis", "analyze_image"]
