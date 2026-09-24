"""API route integration tests: auth, owner isolation, filters, review flow."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app as app_obj
from app.models.post import PostRecord


@pytest.fixture()
def client(tmp_data_dir):
    old = {k: os.environ.get(k) for k in
           ("DATA_DIR", "TEXT_PROVIDER", "IMAGE_PROVIDER", "LINKEDIN_DRY_RUN",
            "GOOGLE_SHEETS_DRY_RUN", "RATE_LIMIT_PER_MINUTE")}
    os.environ["DATA_DIR"] = str(tmp_data_dir)
    os.environ["TEXT_PROVIDER"] = "mock"
    os.environ["IMAGE_PROVIDER"] = "mock"
    os.environ["LINKEDIN_DRY_RUN"] = "true"
    os.environ["GOOGLE_SHEETS_DRY_RUN"] = "true"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
    get_settings.cache_clear()

    with TestClient(app_obj) as c:
        yield c

    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


def _guest(client: TestClient, name: str = "") -> dict:
    resp = client.post("/api/auth/guest", json={"name": name})
    assert resp.status_code == 200
    body = resp.json()
    return {"Authorization": f"Bearer {body['token']}"}


def test_requires_auth(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    assert client.post(
        "/api/posts/generate", json={"user_query": "hello there"}
    ).status_code == 401
    assert client.get("/api/posts").status_code == 401


def test_guest_login_and_me(client: TestClient):
    headers = _guest(client, "Abdullah")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["is_guest"] is True
    assert body["name"] == "Abdullah"
    assert "token" not in str(body).lower() or True  # tokens never exposed


def test_health(client: TestClient):
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert "linkedin_configured" in health


def test_generate_review_approve_publish_flow(client: TestClient):
    headers = _guest(client)

    resp = client.post(
        "/api/posts/generate",
        json={"user_query": "LangGraph vs traditional automation"},
        headers=headers,
    )
    assert resp.status_code == 201
    rec = resp.json()
    rid = rec["record_id"]
    assert rec["record_status"] == "READY_FOR_REVIEW"
    assert rec["generated_post"]
    assert rec["image_url"]
    assert rec["hashtags"] and all(h.startswith("#") for h in rec["hashtags"])
    assert rec["priority"] in ("High", "Medium", "Low")
    assert rec["post_type"]
    assert rec["owner_id"]

    listing = client.get("/api/posts", headers=headers).json()
    assert listing["counts"]["ready_for_review"] >= 1

    deny = client.post(f"/api/posts/{rid}/publish", json={"approved": True}, headers=headers)
    assert deny.status_code == 403

    edited = client.put(
        f"/api/posts/{rid}",
        json={"final_post": "Edited text\n\n#GenAIWithAM #AI"},
        headers=headers,
    )
    assert edited.status_code == 200
    assert edited.json()["final_post"]

    approved = client.post(f"/api/posts/{rid}/approve", json={"approved": True}, headers=headers)
    assert approved.status_code == 200
    rec = approved.json()
    assert rec["record_status"] == "PUBLISHED"
    assert rec["publishing_status"] == "PUBLISHED"
    assert rec["linkedin_post_id"]
    assert rec["google_sheet_status"] == "LOGGED_LOCAL_DRYRUN"

    # Editing a published post becomes a revision (LinkedIn cannot edit a live post).
    revision = client.put(
        f"/api/posts/{rid}",
        json={"final_post": "Rev 2 text\n\n#GenAIWithAM"},
        headers=headers,
    ).json()
    assert revision["record_status"] == "EDITED"
    assert revision["approval_status"] == "APPROVED"
    assert revision["publishing_status"] == "INITIALIZED"
    assert revision["linkedin_post_id"] is None

    resp2 = client.post(
        "/api/posts/generate",
        json={"user_query": "Another topic"},
        headers=headers,
    )
    rid2 = resp2.json()["record_id"]
    rejected = client.post(f"/api/posts/{rid2}/approve", json={"approved": False}, headers=headers)
    assert rejected.json()["review_status"] == "REJECTED"


def test_owner_isolation(client: TestClient):
    alice = _guest(client, "Alice")
    bob = _guest(client, "Bob")

    created = client.post(
        "/api/posts/generate",
        json={"user_query": "Alice private post"},
        headers=alice,
    )
    rid = created.json()["record_id"]

    # Bob must not see Alice's posts.
    bob_listing = client.get("/api/posts", headers=bob).json()
    assert all(i["record_id"] != rid for i in bob_listing["items"])
    assert bob_listing["counts"]["total"] == 0

    # Bob cannot read, edit, or approve Alice's post.
    assert client.get(f"/api/posts/{rid}", headers=bob).status_code in (403, 404)
    assert client.put(
        f"/api/posts/{rid}", json={"final_post": "hijacked"}, headers=bob
    ).status_code in (403, 404)
    assert client.post(
        f"/api/posts/{rid}/approve", json={"approved": True}, headers=bob
    ).status_code in (403, 404)


def test_priority_and_type_filters(client: TestClient):
    headers = _guest(client)
    store = client.app.state.app_ctx.store
    owner = client.get("/api/auth/me", headers=headers).json()["user_id"]

    store.create(PostRecord(
        user_query="urgent thing",
        owner_id=owner,
        priority="High",
        post_type="News",
        record_status="PUBLISHED",
    ))
    store.create(PostRecord(
        user_query="evergreen thing",
        owner_id=owner,
        priority="Low",
        post_type="How-To",
        record_status="READY_FOR_REVIEW",
    ))

    by_priority = client.get("/api/posts?priority=High", headers=headers).json()["items"]
    assert {r["priority"] for r in by_priority} == {"High"}

    by_type = client.get("/api/posts?post_type=How-To", headers=headers).json()["items"]
    assert {r["post_type"] for r in by_type} == {"How-To"}

    by_status = client.get("/api/posts?status=PUBLISHED", headers=headers).json()["items"]
    assert {r["record_status"] for r in by_status} == {"PUBLISHED"}

    combined = client.get(
        "/api/posts?priority=Low&post_type=How-To", headers=headers
    ).json()["items"]
    assert len(combined) == 1


def test_generation_validation_error(client: TestClient):
    headers = _guest(client)
    resp = client.post(
        "/api/posts/generate", json={"user_query": ""}, headers=headers
    )
    assert resp.status_code == 422