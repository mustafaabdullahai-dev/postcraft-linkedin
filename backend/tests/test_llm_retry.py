"""Transient provider faults that must be retried, not surfaced to the user.

Two upstream faults reach `structured()` as raised HTTP errors rather than as
values the attempt loop can inspect:

- 429 rate limits, billed to the whole organisation, so they must be waited out;
- 400 `json_validate_failed`, raised when a reasoning model spends its whole
  output budget thinking and never finishes the JSON document. This one is
  indistinguishable from a genuine schema violation unless it is matched on its
  message, and treating it as fatal turns a transient fault into a hard failure
  for the user.
"""
from __future__ import annotations

import pytest

from app.services.llm import (
    _is_rate_limit_error,
    _is_truncation_error,
    _supports_reasoning_effort,
    _with_rate_limit_retry,
)


class _Status(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


TRUNCATION = (
    "Error code: 400 - {'error': \"{'code': 'json_validate_failed', "
    "'failed_generation': 'max completion tokens reached before generating a "
    "valid document', 'param': 'messages', 'type': 'invalid_request_error'}\"}"
)


def test_truncation_and_rate_limit_are_distinguished():
    assert _is_truncation_error(_Status(TRUNCATION)) is True
    assert _is_rate_limit_error(_Status(TRUNCATION)) is False

    rate = _Status("Error code: 429 - rate_limit_error", status_code=429)
    assert _is_rate_limit_error(rate) is True
    assert _is_truncation_error(rate) is False


def test_truncation_survives_as_error_without_status_code():
    """Groq's truncation error carries no status_code attribute."""
    assert _is_truncation_error(_Status(TRUNCATION)) is True


@pytest.mark.asyncio
async def test_truncation_is_retried_then_recovers(monkeypatch):
    """The regression this guards: truncation used to escape and 400 the user."""
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Status(TRUNCATION)
        return "recovered"

    slept: list[float] = []
    async def fake_sleep(seconds):
        slept.append(seconds)
    monkeypatch.setattr("app.services.llm.asyncio.sleep", fake_sleep)

    result = await _with_rate_limit_retry(flaky, "unit-test")
    assert result == "recovered"
    assert calls["n"] == 3
    # Backoff escalates rather than hammering the provider immediately.
    assert slept == sorted(slept)
    assert len(slept) == 2


@pytest.mark.asyncio
async def test_truncation_gives_up_after_attempts(monkeypatch):
    """After the attempt budget it still raises, so callers see a real error."""
    calls = {"n": 0}

    async def always_truncated():
        calls["n"] += 1
        raise _Status(TRUNCATION)

    async def fake_sleep(seconds):
        return None
    monkeypatch.setattr("app.services.llm.asyncio.sleep", fake_sleep)

    with pytest.raises(_Status):
        await _with_rate_limit_retry(always_truncated, "unit-test")
    assert calls["n"] > 1


@pytest.mark.asyncio
async def test_unrelated_error_is_not_retried():
    """A genuine schema/auth failure must fail fast, not burn the budget."""
    calls = {"n": 0}

    async def boom():
        calls["n"] += 1
        raise _Status("Error code: 401 - invalid api key", status_code=401)

    with pytest.raises(_Status):
        await _with_rate_limit_retry(boom, "unit-test")
    assert calls["n"] == 1


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openai/gpt-oss-120b", True),
        ("openai/gpt-oss-20b", True),
        ("qwen/qwen3.8-27b", True),
        # Non-reasoning models reject the parameter outright.
        ("meta-llama/llama-3.3-70b-versatile", False),
        ("", False),
    ],
)
def test_reasoning_effort_only_sent_to_models_that_support_it(model, expected):
    assert _supports_reasoning_effort(model) is expected