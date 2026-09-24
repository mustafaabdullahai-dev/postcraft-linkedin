"""End-to-end workflow tests: generation → review → approval → publish."""
from __future__ import annotations

import pytest

from app.models.post import PostRecord


@pytest.mark.asyncio
async def test_full_generation_pipeline(app_ctx):
    query = "Explain why Agentic AI is becoming important for modern software engineering."
    record_id = "TEST-000001"

    state = await app_ctx.workflow.run_generation(query, record_id)
    assert state["generated_post"]
    assert state["hashtags"] and all(str(h).startswith("#") for h in state["hashtags"])
    assert state["audience_roles"]
    assert state["author_role"]
    assert state["image_url"]
    assert state["validation_status"] == "VALID"
    assert state["review_status"] in ("PENDING", None)


@pytest.mark.asyncio
async def test_approval_gate_blocks_unapproved_publish(app_ctx):
    record_id = "TEST-000002"
    await app_ctx.workflow.run_generation("topic A", record_id)

    with pytest.raises(PermissionError):
        from app.agents.nodes.content_nodes import publish_to_linkedin

        await publish_to_linkedin(
            {"user_approved": False, "generated_post": "x"},
            ctx=app_ctx.node_context,
        )


@pytest.mark.asyncio
async def test_approve_and_publish_dry_run(app_ctx):
    record_id = "TEST-000003"
    await app_ctx.workflow.run_generation("topic B", record_id)
    state = await app_ctx.workflow.approve_and_publish(
        record_id,
        approved=True,
        resume_update={
            "edited_post": "Edited final post text.",
            "hashtags": ["#DynamicTag"],
        },
    )
    assert state["user_approved"] is True
    assert state["publishing_status"] == "PUBLISHED"
    assert state["linkedin_post_id"]
    assert state["google_sheet_status"]


@pytest.mark.asyncio
async def test_post_record_serde(tmp_data_dir):
    from app.models.post import PostStore

    store = PostStore(tmp_data_dir)
    rec = PostRecord(user_query="test query")
    store.create(rec)
    fetched = store.get(rec.record_id)
    assert fetched is not None
    assert fetched.user_query == "test query"
    assert len(store.list()) == 1


@pytest.mark.asyncio
async def test_generation_failure_then_publish_retry(app_ctx):
    """Publish failure must not destroy the post; retry must work."""
    record_id = "TEST-000004"
    await app_ctx.workflow.run_generation("topic C", record_id)

    class FailingPub:
        async def publish_text_post(self, *a, **k):
            raise RuntimeError("linkedin down")


    old = app_ctx.node_context.linkedin_publisher
    app_ctx.node_context.linkedin_publisher = FailingPub()
    state = await app_ctx.workflow.approve_and_publish(record_id, approved=True)
    assert state["publishing_status"] == "FAILED"

    app_ctx.node_context.linkedin_publisher = old
    statesnap = {
        "record_id": record_id,
        "user_query": "topic C",
        "topic": "topic C",
        "generated_post": "post",
        "edited_post": "post",
        "hashtags": ["#GenAIWithAM"],
    }
    result = await app_ctx.workflow.retry_publish(statesnap)
    assert result["publishing_status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_linkedin_token_refresh_and_persist(app_ctx):
    """Expired access tokens are transparently refreshed and persisted (token rotation)."""
    from datetime import datetime, timedelta, timezone

    import httpx

    from app.models.user import LinkedInUser

    responses = {
        "refresh": {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return responses["refresh"]

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kwargs):
            assert url == "https://www.linkedin.com/oauth/v2/accessToken"
            return FakeResponse()

    def fake_client(*a, **kw):
        return FakeClient()

    app_ctx.node_context.linkedin_publisher._client_id = "id"
    app_ctx.node_context.linkedin_publisher._client_secret = "secret"
    old = httpx.AsyncClient
    httpx.AsyncClient = fake_client
    try:
        user = LinkedInUser(
            name="Test",
            urn="urn:li:person:123",
            access_token="old-access-token",
            refresh_token="old-refresh-token",
            token_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        app_ctx.user_store.save(user)

        token = await app_ctx.node_context.linkedin_publisher.ensure_valid_access_token(
            user, app_ctx.user_store
        )
        assert token == "new-access-token"
        persisted = app_ctx.user_store.get(user.user_id)
        assert persisted.access_token == "new-access-token"
        assert persisted.refresh_token == "new-refresh-token"
    finally:
        httpx.AsyncClient = old


@pytest.mark.asyncio
async def test_linkedin_token_kept_when_not_expired(app_ctx):
    from datetime import datetime, timedelta, timezone

    from app.models.user import LinkedInUser

    user = LinkedInUser(
        name="Test",
        urn="urn:li:person:123",
        access_token="valid-token",
        refresh_token="whatever",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    app_ctx.user_store.save(user)

    token = await app_ctx.node_context.linkedin_publisher.ensure_valid_access_token(
        user, app_ctx.user_store
    )
    assert token == "valid-token"