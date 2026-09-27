from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "LinkedIn AI Content Agent"
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "dev-secret-change-me-in-production"
    frontend_url: str = "http://localhost:5173"

    # Text model
    text_provider: str = "auto"  # auto | openai | anthropic | qwen | groq | openrouter | deepseek | mock
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_text_model: str = "qwen-flash"
    qwen_enable_thinking: bool = False
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    # OpenRouter (OpenAI-compatible aggregator) — any model id, e.g. qwen/qwen3.8-27b
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "qwen/qwen3.8-27b"
    # OpenRouter Dedicated Image API model (e.g. google/gemini-3.1-flash-image-preview)
    openrouter_image_model: str = "google/gemini-3.1-flash-image-preview"
    # "json_schema" (strict) needs openai/gpt-oss-* or qwen/qwen3.8-27b;
    # use "function_calling" for anything that rejects strict schemas.
    openrouter_structured_output_method: str = "json_schema"
    # DeepSeek (OpenAI-compatible) — deepseek-chat for structured work,
    # deepseek-reasoner for open-ended drafting (no tool calls / temperature).
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    # DeepSeek rejects strict "json_schema" response_format; tool calling is the
    # reliable structured-output path, so it does NOT inherit the default below.
    deepseek_structured_output_method: str = "function_calling"
    # function_calling works on all Groq models;
    # json_schema (strict) needs openai/gpt-oss-* or qwen/qwen3.8-27b.
    structured_output_method: str = "function_calling"

    # Image model
    image_provider: str = "auto"  # auto | qwen | openrouter | gemini | mock
    qwen_image_model: str = "wan2.2-t2i-flash"  # flash tier is far faster than wan2.1 turbo queues
    # DashScope-native services endpoint used for async image synthesis + task polling.
    qwen_image_services_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    image_size: str = "1024x1024"
    image_api_key: str = ""
    # Native Google Gemini (generativelanguage.googleapis.com) image generation.
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-3.1-flash-image"
    gemini_image_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Vision review of manually uploaded images (LinkedIn image compliance).
    # "auto" | "qwen" | "gemini" | "off". Empty model = provider default.
    vision_provider: str = "auto"
    vision_model: str = ""

    # LinkedIn
    linkedin_dry_run: bool = True
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""
    linkedin_person_urn: str = ""
    # Multi-user login + publish scope. Uses the official OpenID Connect
    # "Sign in with LinkedIn" scopes (openid/profile/email) + w_member_social
    # so the logged-in user can also publish their approved posts.
    linkedin_scope: str = "openid profile email w_member_social"
    # Leave empty to auto-derive `{frontend_url}/api/auth/linkedin/callback`.
    linkedin_redirect_uri: str = ""

    # Google Sheets
    google_sheets_dry_run: bool = True
    google_service_account_json: str = ""
    google_sheet_id: str = ""

    # Store / data
    data_dir: str = "./data"
    # Max generate/list requests per IP per minute (0 disables).
    rate_limit_per_minute: int = 6

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Security / hardening ──────────────────────────────────
    # IPs whose X-Forwarded-For we trust (the reverse proxy in front of us).
    trusted_proxies: str = "127.0.0.1,::1"
    # Emit hardening response headers on API responses.
    security_headers: bool = True
    content_security_policy: str = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    # /docs, /redoc, /openapi.json. Set false for any public deployment.
    docs_enabled: bool = True
    # Include provider names / modes / environment in GET /api/health. Off by
    # default so a public deployment doesn't advertise its internals.
    health_verbose: bool = False
    # Allow the "continue as guest" demo path. Disable for real public use.
    allow_guest_login: bool = True

    # ── Abuse / cost control (0 = unlimited) ──────────────────
    # Max AI-cost requests per IP per minute (0 disables).
    rate_limit_per_minute: int = 6
    # Per-user daily ceilings on paid calls.
    daily_generations_per_user: int = 0
    daily_images_per_user: int = 0
    # Whole-app daily ceiling on paid calls (runaway-spend circuit breaker).
    global_daily_ai_calls: int = 0

    @field_validator("cors_origins")
    @classmethod
    def _split_origins(cls, v: str) -> str:
        return v.strip()

    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def trusted_proxy_list(self) -> List[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    def production_problems(self) -> List[str]:
        """Security misconfigurations that must block a production boot."""
        if not self.is_production:
            return []
        problems: List[str] = []
        weak = {"", "dev-secret-change-me-in-production", "change-me", "secret"}
        if self.secret_key in weak or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be a unique value of >= 32 characters")
        if "*" in self.cors_origin_list():
            problems.append("CORS_ORIGINS must not include '*'")
        if not self.frontend_url.lower().startswith("https://"):
            problems.append("FRONTEND_URL must use https:// in production")
        if self.docs_enabled:
            problems.append("DOCS_ENABLED must be false in production")
        if self.allow_guest_login:
            problems.append("ALLOW_GUEST_LOGIN must be false in production")
        if self.daily_generations_per_user <= 0 and self.global_daily_ai_calls <= 0:
            problems.append("set DAILY_GENERATIONS_PER_USER and/or GLOBAL_DAILY_AI_CALLS")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()