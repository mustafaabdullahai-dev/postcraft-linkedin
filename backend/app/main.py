"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import main_router_modules
from app.core.abuse import RateLimiter, client_ip
from app.core.config import get_settings
from app.core.context import ApplicationContext
from app.core.logging import (
    _setup_structlog,
    bind_context,
    get_logger,
    new_request_id,
    request_id_var,
    unbind_context,
)
from app.services.scheduler import scheduler_loop

logger = get_logger(__name__)

_boot_settings = get_settings()

# Routes that cost real money (LLM and/or image generation).
_AI_EXACT_PATHS = {"/api/posts/generate", "/api/posts/batch-generate", "/api/posts/suggest"}
_AI_SUFFIXES = ("/suggest-edits", "/rework", "/regenerate", "/regenerate-image")


def _is_ai_path(path: str) -> bool:
    return path in _AI_EXACT_PATHS or (
        path.startswith("/api/posts/") and path.endswith(_AI_SUFFIXES)
    )


def _apply_security_headers(response):
    if not _boot_settings.security_headers:
        return response
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    headers.setdefault("Content-Security-Policy", _boot_settings.content_security_policy)
    if _boot_settings.is_production:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# ─── in-memory rate limiter (per IP sliding window) ──────────
rate_limiter = RateLimiter(per_minute=6)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_structlog(get_settings().log_level)
    settings = get_settings()

    problems = settings.production_problems()
    if problems:
        raise RuntimeError(
            "Refusing to start: production security configuration is incomplete:\n  - "
            + "\n  - ".join(problems)
        )

    app.state.app_ctx = ApplicationContext(settings)
    rate_limiter._per_minute = settings.rate_limit_per_minute
    logger.info("application started", environment=settings.environment)

    scheduler_task = asyncio.create_task(scheduler_loop(app.state.app_ctx))
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("application stopped")


app = FastAPI(
    title=_boot_settings.app_name,
    version="1.0.0",
    description="LangChain + LangGraph LinkedIn content automation with human-in-the-loop publishing.",
    lifespan=lifespan,
    docs_url="/docs" if _boot_settings.docs_enabled else None,
    redoc_url="/redoc" if _boot_settings.docs_enabled else None,
    openapi_url="/openapi.json" if _boot_settings.docs_enabled else None,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = new_request_id()
    request_id_var.set(rid)
    bind_context(request_id=rid, method=request.method, path=request.url.path)
    start = time.perf_counter()

    if _is_ai_path(request.url.path) and rate_limiter._per_minute > 0:
        ip = client_ip(request, _boot_settings.trusted_proxy_list())
        ok, limit = rate_limiter.allow(ip)
        if not ok:
            response = JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in a minute (max {limit}/min)."},
            )
            response.headers["X-Request-Id"] = rid
            return _apply_security_headers(response)

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = rid
        logger.info(
            "http_request",
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return _apply_security_headers(response)
    finally:
        unbind_context()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), cls=exc.__class__.__name__)
    return _apply_security_headers(
        JSONResponse(status_code=500, content={"detail": "Internal server error"})
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=_boot_settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in main_router_modules:
    app.include_router(module.router)


@app.get("/")
async def root():
    return {
        "name": get_settings().app_name,
        "docs": "/docs" if _boot_settings.docs_enabled else None,
        "health": "/api/health",
    }
