"""Provider + node level tests (no external services)."""
from __future__ import annotations

import pytest

from app.models.schemas import ContentPlan, HashtagOutput, LinkedInPostOutput, TopicAnalysis
from app.services.llm import MockTextProvider


@pytest.mark.asyncio
async def test_mock_topic_analysis(app_ctx):
    result = await app_ctx.text_provider.structured(
        TopicAnalysis,
        "",
        "Topic:\nLangGraph vs traditional automation\nUser query:\nLangGraph vs traditional automation",
        topic="LangGraph vs traditional automation",
    )
    assert result.topic
    assert result.audience


@pytest.mark.asyncio
async def test_mock_content_plan(app_ctx):
    result = await app_ctx.text_provider.structured(
        ContentPlan,
        "",
        "Topic: LangGraph",
        topic="LangGraph",
    )
    assert len(result.structure) >= 5


@pytest.mark.asyncio
async def test_mock_post_returns_dynamic_hashtags(app_ctx):
    result = await app_ctx.text_provider.structured(
        LinkedInPostOutput,
        "",
        "Topic: LangGraph\nPlan:\n{}",
        topic="LangGraph",
    )
    assert result.hashtags and all(h.startswith("#") for h in result.hashtags)
    assert result.full_post


@pytest.mark.asyncio
async def test_hashtag_engine_returns_dynamic_tags(app_ctx):
    from app.agents.nodes.content_nodes import generate_hashtags

    state = {
        "user_query": "test",
        "topic": "RAG systems",
        "industry": "Machine Learning",
        "audience": "ML engineers",
        "generated_post": "A post about RAG.",
    }
    result = await generate_hashtags(state, ctx=app_ctx.node_context)
    assert result["hashtags"] and all(h.startswith("#") for h in result["hashtags"])
    assert "#GenAIWithAM" not in result["hashtags"]


@pytest.mark.asyncio
async def test_image_generation_mock(app_ctx):
    from app.agents.nodes.content_nodes import generate_image

    state = {"topic": "Agentic AI", "image_prompt": "a premium AI visual"}
    result = await generate_image(state, ctx=app_ctx.node_context)
    assert result["image_url"].startswith("data:image/svg+xml")
    assert result["image_provider"] == "mock"


@pytest.mark.asyncio
async def test_validation_produces_scores(app_ctx):
    from app.agents.nodes.content_nodes import validate_content

    state = {
        "user_query": "test",
        "generated_post": (
            "Hook line.\n\nBody with real engineering content.\n\nCTA.\n\n#GenAIWithAM"
        ),
        "hashtags": ["#GenAIWithAM"],
    }
    result = await validate_content(state, ctx=app_ctx.node_context)
    assert result["validation_status"] in ("VALID", "INVALID")
    assert "quality_score" in result["validation_result"]


def test_mock_provider_name():
    assert MockTextProvider().name == "mock"


def test_clean_post_removes_stray_hashtag_blocks():
    from app.agents.nodes.content_nodes import clean_post

    raw = (
        "Hook line\n\nBody text.\n\nHashtags:\n#GenAIWithAM #AI\n"
        "Hashtags: #LLM #RAG\n\nA final CTA?\n"
    )
    tags = ["#GenAIWithAM", "#AI", "#LLM", "#RAG"]
    out = clean_post(raw, tags)
    assert "Hashtags:" not in out
    assert out.rstrip().endswith(" #RAG")
    assert out.count("#GenAIWithAM") == 1


def test_clean_post_removes_label_with_tags_inline():
    from app.agents.nodes.content_nodes import clean_post

    raw = "Post body\n\nHashtags: #GenAIWithAM #AI #LLM"
    tags = ["#GenAIWithAM", "#AI", "#LLM"]
    out = clean_post(raw, tags)
    assert "Hashtags:" not in out
    assert out.count("\n") == 2  # body + one blank + tag line