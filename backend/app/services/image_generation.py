"""Image generation providers (Gemini via OpenRouter primary, Qwen fallback, offline mock)."""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ImageResult:
    def __init__(self, image_url: str, provider: str, generated_at: str):
        self.image_url = image_url
        self.provider = provider
        self.generated_at = generated_at


class ImageModelProvider(ABC):
    """Swap Qwen for any OpenAI-compatible image API."""

    name: str = "base"

    @abstractmethod
    async def generate_image(self, prompt: str) -> ImageResult:
        ...


class QwenImageProvider(ImageModelProvider):
    """Qwen image generation.

    Tries the OpenAI-compatible `images/generations` endpoint first (works on
    Qwen Cloud / compatible-mode gateways), then falls back to the DashScope
    native async task API (`services/aigc/text2image` + task polling), which is
    what dashscope-intl / wan2.1-t2i-turbo require.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        model: str = "wan2.1-t2i-turbo",
        size: str = "1024x1024",
        services_url: str = "https://dashscope-intl.aliyuncs.com/api/v1",
        timeout: float = 240.0,
    ):
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model
        self._size = size
        self._services_base = services_url.rstrip("/")
        self._timeout = timeout
        self.name = f"qwen:{model}"

    async def generate_image(self, prompt: str) -> ImageResult:
        try:
            return await self._openai_compatible(prompt)
        except _CompatibleImageUnsupported:
            return await self._dashscope_async(prompt)

    async def _openai_compatible(self, prompt: str) -> ImageResult:
        import httpx

        url = f"{self._base}/images/generations"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "size": self._size,
            "response_format": "b64_json",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (400, 404, 405):
                raise _CompatibleImageUnsupported(resp.status_code)
            resp.raise_for_status()
            data = resp.json()

        return self._items_result(data.get("data") or [])

    async def _dashscope_async(self, prompt: str) -> ImageResult:
        import asyncio
        import httpx

        submit_url = f"{self._services_base}/services/aigc/text2image/image-synthesis"
        payload = {
            "model": self._model,
            "input": {"prompt": prompt},
            "parameters": {"size": self._size.replace("x", "*"), "n": 1},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(submit_url, json=payload, headers=headers)
            resp.raise_for_status()
            task_id = ((resp.json().get("output") or {}).get("task_id") or "")

            # poll
            for _ in range(120):
                await asyncio.sleep(3)
                poll = await client.get(
                    f"{self._services_base}/tasks/{task_id}", headers=headers
                )
                poll.raise_for_status()
                out = poll.json().get("output") or {}
                status = out.get("task_status")
                if status == "SUCCEEDED":
                    return self._items_result(out.get("results") or [])
                if status in ("FAILED", "CANCELED"):
                    raise RuntimeError(f"Qwen image task {status}: {out.get('message') or ''}")

        raise RuntimeError("Qwen image task timed out")

    @staticmethod
    def _items_result(items: list) -> ImageResult:
        if not items:
            raise RuntimeError("Qwen image API returned no image data")
        first = items[0]
        if first.get("b64_json"):
            uri = "data:image/png;base64," + first["b64_json"]
        elif first.get("url"):
            uri = first["url"]
        elif first.get("b64_image"):
            uri = "data:image/png;base64," + first["b64_image"]
        else:
            raise RuntimeError("Qwen image response missing url/b64_json")
        return ImageResult(uri, "qwen-image", _now())


class _CompatibleImageUnsupported(Exception):
    """Endpoint doesn't expose the OpenAI-compatible images/generations route."""

    def __init__(self, status: int):
        super().__init__(f"images/generations unsupported (HTTP {status})")


class OpenRouterImageProvider(ImageModelProvider):
    """OpenRouter Dedicated Image API (POST /api/v1/images)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "google/gemini-3.1-flash-image-preview",
        aspect_ratio: str = "1:1",
        timeout: float = 120.0,
        referer: str = "",
        title: str = "",
    ):
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model
        self._aspect_ratio = aspect_ratio
        self._timeout = timeout
        self._referer = referer
        self._title = title
        self.name = f"openrouter:{model}"

    async def generate_image(self, prompt: str) -> ImageResult:
        import httpx

        url = f"{self._base}/images"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "n": 1,
            "aspect_ratio": self._aspect_ratio,
            "output_format": "png",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._referer:
            headers["HTTP-Referer"] = self._referer
        if self._title:
            headers["X-Title"] = self._title

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("data") or []
        if not items:
            raise RuntimeError("OpenRouter image API returned no image data")

        first = items[0]
        if first.get("b64_json"):
            media_type = first.get("media_type") or "image/png"
            uri = "data:" + media_type + ";base64," + first["b64_json"]
        elif first.get("url"):
            uri = first["url"]
        else:
            raise RuntimeError("OpenRouter image response missing url/b64_json")

        return ImageResult(uri, self.name, _now())


class MockImageProvider(ImageModelProvider):
    """Local SVG placeholder — lets the whole flow run with zero API keys."""

    name = "mock"

    async def generate_image(self, prompt: str) -> ImageResult:
        await _sleep(0.15)
        label = _label(prompt)
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="55%" stop-color="#1e3a8a"/>
      <stop offset="100%" stop-color="#0ea5e9"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="40%" r="60%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1024" height="1024" fill="url(#g)"/>
  <rect width="1024" height="1024" fill="url(#glow)"/>
  <g stroke="#93c5fd" stroke-width="3" fill="none" opacity="0.85">
    <circle cx="512" cy="430" r="150"/>
    <circle cx="270" cy="300" r="70"/>
    <circle cx="760" cy="300" r="70"/>
    <circle cx="300" cy="640" r="70"/>
    <circle cx="730" cy="640" r="70"/>
    <path d="M330 340 L420 400 M690 340 L604 400 M355 610 L430 505 M672 610 L594 505"/>
  </g>
  <circle cx="512" cy="430" r="46" fill="#e0f2fe"/>
  <text x="512" y="760" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="46" font-weight="700" fill="#f8fafc">{label}</text>
  <text x="512" y="812" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="26" fill="#cbd5e1">AI Generated Visual (mock)</text>
</svg>"""
        uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
        return ImageResult(uri, self.name, _now())


class FailoverImageProvider(ImageModelProvider):
    """Tries providers in order and returns the first success (Gemini → Qwen)."""

    def __init__(self, providers: list[ImageModelProvider]):
        self._providers = providers
        self.name = "failover:" + "+".join(p.name for p in providers)

    async def generate_image(self, prompt: str) -> ImageResult:
        errors: list[str] = []
        for provider in self._providers:
            try:
                result = await provider.generate_image(prompt)
                logger.info("image generation succeeded", provider=provider.name)
                return result
            except Exception as exc:  # noqa: BLE001 - failover across providers
                logger.warning(
                    "image provider failed, trying next",
                    provider=provider.name,
                    error=str(exc),
                )
                errors.append(f"{provider.name}: {exc}")
        raise RuntimeError("All image providers failed: " + "; ".join(errors))


def _aspect_ratio(size: str) -> str:
    if "x" in size.lower():
        w, _, h = size.lower().partition("x")
        try:
            return f"{int(w)}:{int(h)}"
        except ValueError:
            return "1:1"
    return "1:1"


def get_image_provider(settings: Settings) -> ImageModelProvider:
    choice = (settings.image_provider or "auto").lower()

    if choice == "mock":
        return MockImageProvider()

    qwen_key = settings.image_api_key or settings.qwen_api_key
    qwen = (
        QwenImageProvider(
            qwen_key,
            settings.qwen_base_url,
            settings.qwen_image_model,
            settings.image_size,
            services_url=settings.qwen_image_services_url,
        )
        if qwen_key
        else None
    )
    openrouter = (
        OpenRouterImageProvider(
            settings.openrouter_api_key,
            settings.openrouter_base_url,
            settings.openrouter_image_model,
            aspect_ratio=_aspect_ratio(settings.image_size),
            referer=settings.frontend_url,
            title=settings.app_name,
        )
        if settings.openrouter_api_key
        else None
    )

    if choice == "qwen":
        if not qwen:
            logger.warning("image provider qwen selected but QWEN_API_KEY missing")
            return MockImageProvider()
        return qwen

    # Gemini (OpenRouter) is the primary image model; Qwen is the backup.
    chain = [p for p in (openrouter, qwen) if p is not None]
    if not chain:
        logger.warning("no image API key configured, falling back to mock")
        return MockImageProvider()
    if len(chain) == 1:
        return chain[0]
    return FailoverImageProvider(chain)


def _now() -> str:
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat()


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def _label(prompt: str) -> str:
    import re

    words = re.findall(r"[A-Za-z0-9+#]+", prompt)[:6]
    label = " ".join(words).upper()
    return (label[:44] or "AI VISUAL")


__all__ = [
    "ImageModelProvider",
    "ImageResult",
    "QwenImageProvider",
    "OpenRouterImageProvider",
    "MockImageProvider",
    "FailoverImageProvider",
    "get_image_provider",
]