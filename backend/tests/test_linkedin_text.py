"""LinkedIn publish-boundary text flattening.

LinkedIn's feed renders shareCommentary.text as plain text (no markdown), so
emphasis markers must be stripped before publishing while the stored post keeps
its markdown for the Google Sheets / CSV exports.
"""
from __future__ import annotations

import pytest

from app.services.linkedin import to_plain_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**bold**", "bold"),
        ("__bold__", "bold"),
        ("***triple***", "triple"),
        ("*italic*", "italic"),
        ("_italic_", "italic"),
        ("~~strike~~", "strike"),
        ("**a** and **b**", "a and b"),
        ("no markup here", "no markup here"),
        ("", ""),
    ],
)
def test_emphasis_is_stripped(raw: str, expected: str):
    assert to_plain_text(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "snake_case_name and my_var",
        "2 * 3 * 4 = 24",
        "a ** b ** c",
        "word* emphasis *word",
        "C:\\path\\to\\file",
    ],
)
def test_non_emphasis_asterisks_and_underscores_survive(raw: str):
    assert to_plain_text(raw) == raw


def test_bullets_become_real_bullets():
    assert to_plain_text("- one\n* two\n+ three") == "• one\n• two\n• three"


def test_headings_and_quotes_lose_their_markers():
    assert to_plain_text("## Heading") == "Heading"
    assert to_plain_text("> quoted") == "quoted"


def test_code_is_left_verbatim():
    fenced = "```\nsome **code** and - dash\n```"
    assert to_plain_text(fenced) == "some **code** and - dash"
    assert to_plain_text("use `**inline**` code") == "use **inline** code"


def test_unbalanced_markers_are_cleaned_up():
    assert to_plain_text("**unclosed bold") == "unclosed bold"


def test_straight_quotes_are_preserved_for_linkedin_to_smart_quote():
    # LinkedIn converts these server-side; the app must not touch them.
    raw = 'Most "our RAG is broken" tickets are **not** LLM problems.'
    assert to_plain_text(raw) == 'Most "our RAG is broken" tickets are not LLM problems.'


def test_publish_text_post_flattens_before_sending(monkeypatch):
    """The flattened text is what reaches shareCommentary.text."""
    import app.services.linkedin as linkedin_module

    settings = linkedin_module.Settings(
        linkedin_dry_run=False,
        linkedin_client_id="id",
        linkedin_client_secret="secret",
    )
    publisher = linkedin_module.LinkedInPublisher(settings)

    captured: dict = {}

    async def fake_post(url, *, json=None, headers=None):
        captured["url"] = url
        captured["text"] = json["specificContent"]["com.linkedin.ugc.ShareContent"][
            "shareCommentary"
        ]["text"]
        captured["headers"] = headers

        class _Resp:
            status_code = 201

            @staticmethod
            def json():
                return {"id": "urn:li:share:123"}

        return _Resp()

    monkeypatch.setattr(linkedin_module.httpx, "AsyncClient", _fake_client(fake_post))

    import asyncio

    asyncio.run(
        publisher._real_publish(
            text="Check **this** out",
            image_url=None,
            access_token="tok",
            person_urn="urn:li:person:abc",
        )
    )

    assert captured["text"] == "Check this out"
    assert captured["url"].endswith("/v2/ugcPosts")


class _fake_client:
    def __init__(self, post_impl):
        self._post = post_impl

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, json=None, headers=None):
        return await self._post(url, json=json, headers=headers)
