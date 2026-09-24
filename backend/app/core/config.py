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
    text_provider: str = "auto"  # auto | openai | anthropic | qwen | groq | openrouter | mock
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

    @field_validator("cors_origins")
    @classmethod
    def _split_origins(cls, v: str) -> str:
        return v.strip()

    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()