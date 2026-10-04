"""Deterministic text overlay for generated images.

Image models cannot spell, so the headline is drawn by a real font rasteriser
instead of being asked of the model. That is only worth anything if the drawn
text is guaranteed to equal the requested text, in the requested script — which
is what these tests pin down.
"""
from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app.services.image_overlay import (
    _font_stack,
    _load_font,
    _resolve_font_file,
    _wrap,
    detect_script,
    overlay_result_url,
    render_text_overlay,
)

SAMPLES = {
    "latin": "AI AGENTS",
    "mixed_case": "MLOps Kubernetes SaaS",
    "arabic": "الذكاء الاصطناعي",
    "devanagari": "कृत्रिम बुद्धिमत्ता",
    "cjk": "人工智能代理",
    "long": "How agentic AI is reshaping engineering teams",
}


def _canvas(width: int = 1200, height: int = 628) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (14, 22, 46)).save(buffer, format="PNG")
    return buffer.getvalue()


def _ink_ratio(png: bytes) -> float:
    """Share of non-background pixels, used to prove text was actually drawn."""
    with Image.open(io.BytesIO(png)) as img:
        grey = img.convert("L")
    hist = grey.histogram()
    total = sum(hist)
    background = max(hist)
    return (total - background) / total


@pytest.mark.parametrize(
    "text,expected",
    [
        ("AI AGENTS", "latin"),
        ("Hello world", "latin"),
        ("مرحبا", "arabic"),
        ("שלום", "hebrew"),
        ("नमस्ते", "devanagari"),
        ("人工智能", "cjk"),
        ("こんにちは", "cjk"),
        ("12345 !?", "latin"),
    ],
)
def test_detect_script_picks_a_font_with_real_glyphs(text, expected):
    script = detect_script(text)
    assert script == expected

    family = next((f for f in _font_stack(script) if _resolve_font_file(f)), None)
    assert family, f"no font resolves for script {script!r}"

    font = _load_font(family, 64)
    # A missing glyph renders as .notdef. U+FFFD is absent from essentially
    # every font, so its mask is the tofu signature to compare against.
    tofu = font.getmask("\uFFFD", mode="L")
    tofu_sig = (tofu.size, bytes(tofu).__hash__())
    for char in {c for c in text if not c.isspace()}:
        mask = font.getmask(char, mode="L")
        assert (mask.size, bytes(mask).__hash__()) != tofu_sig, (
            f"{script}: {char!r} has no glyph in {family}"
        )


@pytest.mark.parametrize("label", sorted(SAMPLES))
def test_overlay_renders_text_for_every_script(label):
    out = render_text_overlay(_canvas(), SAMPLES[label], "bottom")
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "PNG"
    assert _ink_ratio(out) > 0.001, "no visible text was drawn"


@pytest.mark.parametrize("label", sorted(SAMPLES))
def test_render_is_deterministic(label):
    """Identical input must give byte-identical output, so a re-roll is auditable."""
    canvas = _canvas()
    first = render_text_overlay(canvas, SAMPLES[label])
    second = render_text_overlay(canvas, SAMPLES[label])
    assert first == second


def test_overlay_actually_changes_the_pixels():
    canvas = _canvas()
    assert render_text_overlay(canvas, "AI AGENTS") != canvas


def test_placement_moves_the_text_band():
    canvas = _canvas()
    top = render_text_overlay(canvas, "HEADLINE", "top")
    bottom = render_text_overlay(canvas, "HEADLINE", "bottom")
    assert top != bottom

    def upper_ink(png: bytes) -> float:
        with Image.open(io.BytesIO(png)) as img:
            band = img.convert("L").crop((0, 0, img.width, img.height // 3))
        hist = band.histogram()
        return (sum(hist) - max(hist)) / sum(hist)

    assert upper_ink(top) > upper_ink(bottom)


def test_empty_text_is_a_no_op():
    canvas = _canvas()
    assert render_text_overlay(canvas, "") == canvas
    assert render_text_overlay(canvas, "   \n\t ") == canvas


def test_unreadable_image_returns_input_instead_of_raising():
    """A font or decode problem must never take down image generation."""
    junk = b"\x00\x01definitely-not-a-png"
    assert render_text_overlay(junk, "HELLO") == junk


def test_wrapping_respects_max_width():
    font = _load_font("Liberation Sans", 48)
    lines = _wrap("alpha beta gamma delta epsilon zeta eta theta", font, 400, False)
    assert len(lines) > 1
    assert all(font.getbbox(line)[2] <= 400 for line in lines)


def test_overlay_result_url_handles_data_urls():
    canvas = _canvas()
    data_url = "data:image/png;base64," + base64.b64encode(canvas).decode()
    out = overlay_result_url(data_url, "AI AGENTS")
    assert out.startswith("data:image/png;base64,")
    decoded = base64.b64decode(out.split(",", 1)[1])
    assert decoded != canvas


def test_overlay_result_url_handles_raw_base64():
    canvas = _canvas()
    raw = base64.b64encode(canvas).decode()
    out = overlay_result_url(raw, "AI AGENTS")
    assert base64.b64decode(out) != canvas


def test_overlay_result_url_leaves_unknown_input_alone():
    assert overlay_result_url("https://example.com/a.png", "AI AGENTS") == (
        "https://example.com/a.png"
    )
    assert overlay_result_url("", "AI AGENTS") == ""