"""Structured-output resilience: provider emits unparseable tool-call arguments.

DeepSeek intermittently copies straight double quotes out of the source post
into function-call arguments without escaping them, producing invalid JSON that
LangChain discards (`invalid_tool_calls`) and `with_structured_output` reports
as None. These tests cover the repair + retry path in LangChainTextProvider.
"""
from __future__ import annotations

import json

import pytest

from app.models.schemas import PostEditSuggestions
from app.services.llm import (
    STRUCTURED_ATTEMPTS,
    LangChainTextProvider,
    _recover_structured,
    repair_unescaped_quotes,
)


def test_repair_escapes_bare_quotes_inside_values():
    broken = (
        '{"summary": "ok", "notes": ["Most "our RAG is broken" tickets are retrieval '
        'issues"], "improved_draft": "body"}'
    )
    fixed = repair_unescaped_quotes(broken)
    assert fixed is not None
    parsed = json.loads(fixed)
    assert parsed["notes"] == ['Most "our RAG is broken" tickets are retrieval issues']


def test_repair_keeps_keys_and_structure_intact():
    broken = '{"summary": "s", "notes": ["he said "hi" loudly"], "improved_draft": "d"}'
    parsed = json.loads(repair_unescaped_quotes(broken))
    assert parsed["summary"] == "s"
    assert parsed["notes"] == ['he said "hi" loudly']
    assert parsed["improved_draft"] == "d"


def test_repair_handles_escaped_quotes_without_double_escaping():
    valid = json.dumps({"summary": 'he said "hi"', "notes": [], "improved_draft": "d"})
    assert repair_unescaped_quotes(valid) is None  # already valid -> no repair


def test_repair_returns_none_when_unfixable():
    assert repair_unescaped_quotes("not json at all {{{") is None
    assert repair_unescaped_quotes("") is None
    assert repair_unescaped_quotes(None) is None  # type: ignore[arg-type]


def test_recover_uses_repaired_args_and_validates_against_schema():
    broken = (
        '{"summary": "tighten the hook", "notes": ["Most "our RAG is broken" tickets"], '
        '"improved_draft": "rewritten body"}'
    )

    class _Raw:
        invalid_tool_calls = [{"name": "PostEditSuggestions", "args": broken, "id": "call_1"}]
        tool_calls: list = []

    out = _recover_structured(_Raw(), PostEditSuggestions)
    assert isinstance(out, PostEditSuggestions)
    assert out.summary == "tighten the hook"
    assert out.notes == ['Most "our RAG is broken" tickets']
    assert out.improved_draft == "rewritten body"


def test_recover_returns_none_when_nothing_validates():
    class _Raw:
        invalid_tool_calls = [{"args": '{"summary": "missing required field"}'}]

    assert _recover_structured(_Raw(), PostEditSuggestions) is None
    assert _recover_structured(None, PostEditSuggestions) is None


class _FakeChain:
    """Stands in for a with_structured_output chain."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        return self._outcomes.pop(0)


class _FakeModel:
    def __init__(self, outcomes):
        self.chain = _FakeChain(outcomes)
        self.bound_schema = None

    def with_structured_output(self, schema, method, include_raw):
        assert include_raw is True, "retry loop needs include_raw=True"
        self.bound_schema = schema
        return self.chain


def _provider(outcomes):
    return LangChainTextProvider(_FakeModel(outcomes), name="fake")


@pytest.mark.asyncio
async def test_structured_returns_parsed_result_without_retrying():
    parsed = PostEditSuggestions(summary="s", notes=[], improved_draft="d")
    model = _FakeModel([{"raw": None, "parsed": parsed, "parsing_error": None}])
    provider = LangChainTextProvider(model, name="fake")
    out = await provider.structured(PostEditSuggestions, "sys", "human")
    assert out is parsed
    assert model.chain.calls == 1


@pytest.mark.asyncio
async def test_structured_recovers_from_invalid_tool_call():
    broken = (
        '{"summary": "s", "notes": ["a "b" c"], "improved_draft": "d"}'
    )

    class _Raw:
        invalid_tool_calls = [{"args": broken}]

    model = _FakeModel(
        [{"raw": _Raw(), "parsed": None, "parsing_error": "Expecting ',' delimiter"}]
    )
    provider = LangChainTextProvider(model, name="fake")
    out = await provider.structured(PostEditSuggestions, "sys", "human")
    assert out.notes == ['a "b" c']
    assert model.chain.calls == 1  # repaired, no retry needed


@pytest.mark.asyncio
async def test_structured_retries_then_succeeds():
    good = PostEditSuggestions(summary="s2", notes=[], improved_draft="d2")
    model = _FakeModel(
        [
            {"raw": None, "parsed": None, "parsing_error": "boom"},
            {"raw": None, "parsed": None, "parsing_error": "boom"},
            {"raw": None, "parsed": good, "parsing_error": None},
        ]
    )
    provider = LangChainTextProvider(model, name="fake")
    out = await provider.structured(PostEditSuggestions, "sys", "human")
    assert out is good
    assert model.chain.calls == 3


@pytest.mark.asyncio
async def test_structured_raises_clear_error_after_exhausting_attempts():
    model = _FakeModel(
        [{"raw": None, "parsed": None, "parsing_error": "boom"}] * STRUCTURED_ATTEMPTS
    )
    provider = LangChainTextProvider(model, name="fake")
    with pytest.raises(ValueError, match="PostEditSuggestions"):
        await provider.structured(PostEditSuggestions, "sys", "human")
    assert model.chain.calls == STRUCTURED_ATTEMPTS


@pytest.mark.asyncio
async def test_structured_never_surfaces_the_old_none_error():
    """The reported bug: model_validate(None) must never be reached."""
    model = _FakeModel([{"raw": None, "parsed": None, "parsing_error": "x"}] * 3)
    provider = LangChainTextProvider(model, name="fake")
    with pytest.raises(ValueError) as exc:
        await provider.structured(PostEditSuggestions, "sys", "human")
    assert "Input should be a valid dictionary" not in str(exc.value)
