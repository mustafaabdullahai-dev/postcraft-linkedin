"""Emoji counting + structure rules.

Regression cover for the bug where numbered keycap list markers (1️⃣..5️⃣)
were invisible to the counter, so a post showing 8 emoji validated as 3.
"""
from __future__ import annotations

import pytest

from app.services.validator import KEYCAP_RUN_RE, ValidationRules, count_emojis


def test_keycap_markers_are_counted():
    # 5 keycaps + 3 pictographs = 8, the way a reader sees it.
    text = "1\uFE0F\u20E3 a 2\uFE0F\u20E3 b 3\uFE0F\u20E3 c 4\uFE0F\u20E3 d 5\uFE0F\u20E3 e \U0001F680 \U0001F916 \U0001F4CA."
    assert count_emojis(text) == 8


def test_plain_text_has_no_emoji():
    assert count_emojis("no emoji here at all") == 0


def test_zwj_family_counts_once():
    assert count_emojis("a \U0001F468\u200D\U0001F469\u200D\U0001F467 b") == 1


def test_adjacent_emoji_count_separately():
    assert count_emojis("x \U0001F680\U0001F916\U0001F4CA y") == 3


def test_flag_pair_counts_once():
    assert count_emojis("hi \U0001F1F5\uFE0F\U0001F1F0 there") == 1


def test_variation_selector_and_skin_tone():
    assert count_emojis("love \u2764\uFE0F ok") == 1
    assert count_emojis("thumbs \U0001F44D\U0001F3FD ok") == 1


def test_keycap_run_detected_on_one_line():
    line = "Five steps: 1\uFE0F\u20E3 one 2\uFE0F\u20E3 two 3\uFE0F\u20E3 three"
    assert KEYCAP_RUN_RE.search(line)


def test_keycap_run_not_detected_when_split_per_line():
    body = "1\uFE0F\u20E3 one\n2\uFE0F\u20E3 two\n3\uFE0F\u20E3 three"
    assert not any(KEYCAP_RUN_RE.search(l) for l in body.splitlines())


def _long_enough(tags=("#AI", "#Automation", "#SaaS", "#Product", "#Growth")):
    filler = "Useful detail for the team to consider carefully. " * 12
    return filler + " " + " ".join(tags)


def test_low_emoji_count_is_advisory_not_blocking():
    body = _long_enough() + " Done."
    tags = list(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))
    rules = ValidationRules(body, tags, emojis_enabled=True)
    # Style preference, so it must not invalidate the post.
    assert not any("emoji" in i.lower() for i in rules.blocking_issues())
    assert any("house style is 3-7" in s for s in rules.style_suggestions())


def test_no_emoji_advice_when_toggle_off():
    body = _long_enough() + " Done."
    tags = list(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))
    rules = ValidationRules(body, tags, emojis_enabled=False)
    assert rules.style_suggestions() == []


def test_emoji_present_while_toggle_off_is_flagged():
    body = _long_enough() + " Ship it \U0001F680 \U0001F916 \U0001F4CA"
    issues = ValidationRules(body, list(("#AI", "#Automation", "#SaaS", "#Product", "#Growth")), emojis_enabled=False).blocking_issues()
    assert any("emoji toggle is off" in i for i in issues)


def test_crammed_keycap_list_is_flagged():
    body = (
        "AI agents change support workflows. A reliable rollout follows five steps: "
        "1\uFE0F\u20E3 map decisions, 2\uFE0F\u20E3 pick a model, 3\uFE0F\u20E3 hook the API, "
        "4\uFE0F\u20E3 add a human check, 5\uFE0F\u20E3 monitor. "
        "Teams that follow this ship faster. Ship it \U0001F680 and review \U0001F916 then tune \U0001F4CA."
    )
    body = body + " " + " ".join(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))
    issues = ValidationRules(body, list(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))).blocking_issues()
    assert any("crammed into one line" in i for i in issues)


def test_split_keycap_list_not_flagged():
    body = (
        "AI agents change support workflows. A reliable rollout follows five steps.\n"
        "1\uFE0F\u20E3 map repeatable decisions\n"
        "2\uFE0F\u20E3 pick a model\n"
        "3\uFE0F\u20E3 hook the API\n"
        "4\uFE0F\u20E3 add a human check\n"
        "5\uFE0F\u20E3 monitor and tune \U0001F680\n"
        "Teams that follow this ship faster, review \U0001F916 and tune \U0001F4CA."
    )
    body = body + " " + " ".join(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))
    issues = ValidationRules(body, list(("#AI", "#Automation", "#SaaS", "#Product", "#Growth"))).blocking_issues()
    assert not any("crammed into one line" in i for i in issues)
