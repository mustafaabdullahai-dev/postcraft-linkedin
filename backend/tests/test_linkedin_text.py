"""LinkedIn publish-boundary text normalisation.

LinkedIn's feed renders shareCommentary.text as plain text (no markdown parser),
but it *does* render Unicode bulge characters. So `**bold**` is converted to real
bold Unicode rather than dropped — the emphasis survives on the feed — while the
stored post keeps its markdown for the Google Sheets / CSV exports.
"""
from __future__ import annotations

import pytest

from app.services.linkedin import to_linkedin_text, to_unicode_bold

BOLD = "\U0001D41B\U0001D428\U0001D425\U0001D41D"  # "bold"
BOLD_TRIPLE = "\U0001D42D\U0001D42B\U0001D422\U0001D429\U0001D425\U0001D41E"  # "triple"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**bold**", BOLD),
        ("__bold__", BOLD),
        ("***triple***", BOLD_TRIPLE),
        ("*italic*", "italic"),
        ("_italic_", "italic"),
        ("~~strike~~", "strike"),
        ("**a** and **b**", "\U0001D41A and \U0001D41B"),
        ("no markup here", "no markup here"),
        ("", ""),
    ],
)
def test_emphasis_becomes_real_bold(raw: str, expected: str):
    assert to_linkedin_text(raw) == expected


def test_to_unicode_bold_maps_ascii_only():
    assert to_unicode_bold("Az9!") == "\U0001D400\U0001D433\U0001D7D7!"
    assert to_unicode_bold("café") == "\U0001D41C\U0001D41A\U0001D41Fé"


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
    assert to_linkedin_text(raw) == raw


def test_bullets_become_real_bullets():
    assert to_linkedin_text("- one\n* two\n+ three") == "• one\n• two\n• three"


def test_headings_and_quotes_lose_their_markers():
    assert to_linkedin_text("## Heading") == "Heading"
    assert to_linkedin_text("> quoted") == "quoted"


def test_code_is_left_verbatim():
    fenced = "```\nsome **code** and - dash\n```"
    assert to_linkedin_text(fenced) == "some **code** and - dash"
    assert to_linkedin_text("use `**inline**` code") == "use **inline** code"


def test_unbalanced_markers_are_cleaned_up():
    assert to_linkedin_text("**unclosed bold") == "unclosed bold"


def test_straight_quotes_are_preserved_for_linkedin_to_smart_quote():
    # LinkedIn converts these server-side; the app must not touch them.
    raw = 'Most "our RAG is broken" tickets are **not** LLM problems.'
    assert to_linkedin_text(raw) == (
        'Most "our RAG is broken" tickets are \U0001D427\U0001D428\U0001D42D LLM problems.'
    )


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

    assert captured["text"] == "Check \U0001D42D\U0001D421\U0001D422\U0001D42C out"
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
