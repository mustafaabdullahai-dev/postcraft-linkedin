from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

import structlog

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Keys whose values must never reach a log sink in cleartext.
_REDACT_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "set-cookie",
    "secret",
    "secret_key",
    "client_secret",
    "api_key",
    "apikey",
    "password",
    "code",
    "state",
}

_REDACTED = "[redacted]"


def redact_secrets(logger, method_name, event_dict):
    """structlog processor: blank out anything that looks like a credential."""
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def _setup_structlog(level: str = "INFO") -> None:
    handlers = [logging.StreamHandler(sys.stdout)]

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_secrets,
        ],
    )

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            redact_secrets,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level.upper())


def get_logger(name: str | None = None):
    return structlog.get_logger(name or "linkedin-poster")


def bind_context(**kwargs) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(**_) -> None:
    # Clear all contextvars for this request (they're per-event loop tasks).
    structlog.contextvars.unbind_contextvars()


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


logger = structlog.get_logger()

__all__ = [
    "logger",
    "get_logger",
    "bind_context",
    "unbind_context",
    "new_request_id",
    "request_id_var",
    "_setup_structlog",
]