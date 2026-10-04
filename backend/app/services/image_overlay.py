"""Deterministic text overlay for generated images.

Image models cannot reliably spell. Diffusion- and video-based generators
treat letterforms as texture, so a prompt that asks for "AI AGENTS" yields
something letter-shaped rather than the word, and spelling it out
character-by-character ("A-I  A-G-E-N-T-S") mostly trades a misspelling for
stray hyphens. No prompt phrasing fixes this.

So the image is generated without any lettering and the words are drawn here,
by a real font rasteriser. That makes the result exact by construction, in any
script, for free and offline. It also buys real typographic control —
wrapping, optical sizing and contrast handling that no image model exposes.

Pillow is already a project dependency and this host has the Noto families, so
raqm-based shaping covers Arabic, Hebrew, Devanagari, Bengali, Tamil and CJK
without extra packages.
"""
from __future__ import annotations

import base64
import io
import subprocess
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.core.logging import get_logger

logger = get_logger(__name__)

RGB = Tuple[int, int, int]

# Preference order per script. Resolved through fontconfig so aliases and
# variable fonts work; the first family that actually resolves wins.
_SCRIPT_FONT_STACKS: Sequence[Tuple[str, Sequence[str]]] = (
    ("arabic", ("Noto Naskh Arabic", "Noto Sans Arabic", "DejaVu Sans")),
    ("hebrew", ("Noto Sans Hebrew", "DejaVu Sans")),
    ("devanagari", ("Noto Sans Devanagari", "Noto Serif Devanagari")),
    ("bengali", ("Noto Sans Bengali", "Noto Serif Bengali")),
    ("tamil", ("Noto Sans Tamil", "DejaVu Sans")),
    ("cjk", ("Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC")),
    ("thai", ("Noto Sans Thai", "DejaVu Sans")),
    ("latin", ("Liberation Sans", "DejaVu Sans", "Adwaita Sans", "Noto Sans")),
)

# Unicode block starts per script, checked in order.
_SCRIPT_RANGES = {
    "arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF)),
    "hebrew": ((0x0590, 0x05FF),),
    "devanagari": ((0x0900, 0x097F),),
    "bengali": ((0x0980, 0x09FF),),
    "tamil": ((0x0B80, 0x0BFF),),
    "cjk": ((0x3040, 0x30FF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF)),
    "thai": ((0x0E00, 0x0E7F),),
}

# CJK wraps between any two glyphs rather than only at spaces.
_NO_SPACE_BREAK = {"cjk"}

DEFAULT_FONT_COLOR: RGB = (255, 255, 255)
_SCRIM_COLOR: RGB = (8, 12, 20)

MIN_FONT_SIZE = 18
MAX_FONT_SIZE = 132
_FONT_SIZE_STEP = 4
_LINE_SPACING = 1.18


def detect_script(text: str) -> str:
    """Return the script key that governs font choice for `text`."""
    for char in text:
        code = ord(char)
        if code < 0x0080:
            continue
        for script, ranges in _SCRIPT_RANGES.items():
            if any(start <= code <= end for start, end in ranges):
                return script
    return "latin"


@lru_cache(maxsize=64)
def _resolve_font_file(family: str, bold: bool = True) -> Optional[str]:
    """Ask fontconfig for a concrete font file, or None if unavailable."""
    pattern = f"{family}:bold" if bold else family
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}", pattern],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("fontconfig lookup failed", family=family, error=str(exc))
        return None
    path = (out.stdout or "").strip()
    return path or None


@lru_cache(maxsize=256)
def _load_font(family: str, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load `family` at `size`, applying a variable font's weight axis."""
    path = _resolve_font_file(family, bold)
    if not path:
        raise FileNotFoundError(f"no font file for {family!r}")
    font = ImageFont.truetype(path, size)
    # Variable fonts ship one file for all weights; ask for the bold master so
    # headlines do not render at regular weight.
    if bold and getattr(font, "set_variation_by_axes", None):
        try:
            font.set_variation_by_axes([700.0])
        except (OSError, ValueError):
            pass
    return font


def _font_stack(script: str) -> Sequence[str]:
    for key, stack in _SCRIPT_FONT_STACKS:
        if key == script:
            return stack
    return _SCRIPT_FONT_STACKS[-1][1]


def _measure(font: ImageFont.FreeTypeFont, text: str) -> Tuple[int, int]:
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int, any_break: bool) -> List[str]:
    """Greedy line wrap. `any_break` splits between glyphs for CJK."""
    words: List[str] = list(text) if any_break else text.split()
    if not words:
        return []
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + (" " if not any_break else "") + word
        width, _ = _measure(font, candidate)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit(
    text: str,
    families: Sequence[str],
    max_width: int,
    max_height: int,
    max_lines: int,
    any_break: bool,
) -> Tuple[Optional[ImageFont.FreeTypeFont], List[str]]:
    """Largest size at which `text` fits the box, or (None, []) if none does."""
    fallback: Optional[Tuple[ImageFont.FreeTypeFont, List[str]]] = None
    for family in families:
        size = MAX_FONT_SIZE
        while size >= MIN_FONT_SIZE:
            try:
                font = _load_font(family, size)
            except (FileNotFoundError, OSError):
                break  # family unavailable; try the next candidate
            lines = _wrap(text, font, max_width, any_break)
            if len(lines) <= max_lines:
                line_h = _measure(font, "Ag")[1]
                if line_h * len(lines) * _LINE_SPACING <= max_height:
                    return font, lines
            fallback = fallback or (font, lines[:max_lines])
            size -= _FONT_SIZE_STEP
    return fallback if fallback else (None, [])


def _scrim(height: int, band_height: int) -> Image.Image:
    """Vertical dark gradient so light text stays legible on any artwork."""
    band = Image.new("RGBA", (1, band_height), (0, 0, 0, 0))
    pixels = band.load()
    for y in range(band_height):
        # Ease-in so the top of the band fades in rather than cutting hard.
        t = (y / max(1, band_height - 1)) ** 1.6
        pixels[0, y] = (*_SCRIM_COLOR, int(216 * t))
    return band.resize((height, band_height))


def render_text_overlay(
    image_bytes: bytes,
    text: str,
    placement: str = "bottom",
    color: RGB = DEFAULT_FONT_COLOR,
    max_lines: int = 3,
    max_width_ratio: float = 0.84,
) -> bytes:
    """Draw `text` onto `image_bytes` and return PNG bytes.

    Never raises: on any failure the original image is returned unchanged, so
    a font problem cannot take down image generation.
    """
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return image_bytes
    try:
        with Image.open(io.BytesIO(image_bytes)) as src:
            image = src.convert("RGBA")

        width, height = image.size
        script = detect_script(cleaned)
        families = _font_stack(script)
        any_break = script in _NO_SPACE_BREAK

        margin = max(16, int(min(width, height) * 0.06))
        box_w = int(width * max_width_ratio)
        box_h = int(height * 0.34)
        font, lines = _fit(cleaned, families, box_w, box_h, max_lines, any_break)
        if font is None or not lines:
            logger.warning("no font could fit overlay text", script=script)
            return image_bytes

        line_h = _measure(font, "Ag")[1]
        gap = int(line_h * (_LINE_SPACING - 1))
        block_h = line_h * len(lines) + gap * (len(lines) - 1)

        top = (
            margin
            if placement.lower() in {"top", "upper"}
            else height - margin - block_h
        )
        left = (width - box_w) // 2

        scrim = Image.new("RGBA", image.size, (0, 0, 0, 0))
        band_h = min(height, block_h + margin * 2)
        band_top = 0 if placement.lower() in {"top", "upper"} else height - band_h
        scrim.paste(_scrim(width, band_h), (0, band_top))
        image = Image.alpha_composite(image, scrim)

        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            line_w, _ = _measure(font, line)
            draw.text(
                (left + (box_w - line_w) // 2, top + index * (line_h + gap)),
                line,
                font=font,
                fill=(*color, 255),
            )

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("overlay render failed, returning original image", error=str(exc))
        return image_bytes


def overlay_result_url(image_url: str, text: str, placement: str = "bottom") -> str:
    """Apply the overlay to a data: or base64 image URL, tolerating both forms."""
    if not text:
        return image_url
    try:
        if image_url.startswith("data:"):
            header, _, payload = image_url.partition(",")
            if not payload:
                return image_url
            raw = base64.b64decode(payload)
            updated = render_text_overlay(raw, text, placement)
            return f"{header},{base64.b64encode(updated).decode('ascii')}"
        raw = base64.b64decode(image_url, validate=True)
    except (ValueError, TypeError):
        return image_url
    return base64.b64encode(render_text_overlay(raw, text, placement)).decode("ascii")