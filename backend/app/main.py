"""FastAPI application entrypoint."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Dict, List, Tuple

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import main_router_modules
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

logger = get_logger(__name__)


# ─── in-memory rate limiter (per IP sliding window) ──────────
class RateLimiter:
    def __init__(self, per_minute: int = 6):
        self._per_minute = per_minute
        self._hits: Dict[str, List[float]] = {}

    def allow(self, key: str) -> Tuple[bool, int]:
        now = time.monotonic()
        window = 60.0
        hits = [t for t in self._hits.get(key, []) if now - t < window]
        hits.append(now)
        self._hits[key] = hits
        return (len(hits) <= self._per_minute, self._per_minute)


rate_limiter = RateLimiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_structlog(get_settings().log_level)
    settings = get_settings()
    app.state.app_ctx = ApplicationContext(settings)
    rate_limiter._per_minute = settings.rate_limit_per_minute
    logger.info("application started", environment=settings.environment)
    yield
    logger.info("application stopped")


app = FastAPI(
    title=get_settings().app_name,
    version="1.0.0",
    description="LangChain + LangGraph LinkedIn content automation with human-in-the-loop publishing.",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = new_request_id()
    request_id_var.set(rid)
    bind_context(request_id=rid, method=request.method, path=request.url.path)
    start = time.perf_counter()

    if request.url.path in ("/api/posts/generate", "/api/posts") and rate_limiter._per_minute > 0:
        ip = request.client.host if request.client else "unknown"
        ok, limit = rate_limiter.allow(ip)
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in a minute (max {limit}/min)."},
            )

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = rid
        logger.info(
            "http_request",
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return response
    finally:
        unbind_context()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), cls=exc.__class__.__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


_settings_for_middleware = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings_for_middleware.cors_origin_list(),
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
        "docs": "/docs",
        "health": "/api/health",
    }