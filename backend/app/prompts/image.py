"""Prompts: hashtag engine + image prompt generation."""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from app.models.schemas import HashtagOutput, ImagePromptOutput
from app.prompts.guidelines import image_rules_text

# ── Hashtags ──────────────────────────────────────────────────
HASHTAG_SYSTEM = """You are a LinkedIn hashtag strategist.

Generate 5-10 hashtags for this post — FRESH every time, built entirely from the
post's specific topic, its niche/industry and its role-based audience. Never
reuse an unrelated or personal tag.

Rules:
1. NO fixed, personal or brand hashtags (no #GenAIWithAM, #YourBrand, etc.).
2. Every tag must be genuinely relevant to THIS exact post: its niche, its
   industry/community and the concrete terms inside it.
3. Mix 1-2 broad reachable tags + 2-4 tightly-specific niche tags + optional
   role/community tags. The mix must change per query — never a template.
4. Use conventional CamelCase for recognized compounds (#LinkedInGrowth not
   #linkedingrowth), avoid ALL-CAPS and hashtag stuffing, no lazy filler.
5. 5-10 tags that look real and efficient on LinkedIn.
6. LANGUAGE: hashtags must be in the SAME language as the post when that
   language uses a Latin or Arabic script. For scripts LinkedIn cannot index in
   hashtags (Chinese, Japanese, Korean), keep hashtags in English.
"""

HASHTAG_HUMAN = """Topic: {topic}
Industry/community: {industry}
Target audience: {audience}
Post language (write tags in this language when its script allows hashtags):
{language}
Post:
{post}"""

hashtag_prompt = ChatPromptTemplate.from_messages(
    [("system", HASHTAG_SYSTEM), ("human", HASHTAG_HUMAN)]
)

HashtagSchema = HashtagOutput

# ── Image prompt ──────────────────────────────────────────────
# Shared by the initial concept and the regeneration concept. Both must enforce
# identical text rendering rules, otherwise a regenerated image silently loses
# the spelling guarantees the first one had.
TEXT_RENDERING_RULES = """HOW TO WRITE TEXT INTO THE IMAGE PROMPT (critical — follow exactly):

These rules govern how you must WRITE the `image_prompt` field itself, not how
you describe the topic. Image models render text unreliably unless the prompt
makes the characters unambiguous.

1. Separate the text from the visual description, and put the exact text in
   quotation marks or ALL CAPS so the model can tell lettering apart from
   scene description.
   • Good: A clean, modern technology logo. The image features a sleek digital
     brain icon. Below the icon, the literal text "AI AGENTS" must be cleanly
     printed in a bold, white sans-serif font.
   • Bad: A logo about AI agents with some text.

2. For words that image models frequently misread, force the model to attend to
   the individual characters by spelling them out in the prompt.
   • Good: A neon sign on a dark wall that reads "A-I  A-G-E-N-T-S".
   • Use this for acronym-like or invented words (AI, AGENTS, SaaS, Kubernetes,
     MLOps) and for any word in a non-Latin script the model is likely to
     garble. Do NOT spell out ordinary English words — it makes them worse.

3. State the text's placement, font, colour and size explicitly ("bottom
   centre", "bold white sans-serif", "large, filling the lower third"), and say
   it must be printed cleanly and legibly.

4. Repeat the required language explicitly when the image carries any text.

5. Prefer an entirely text-free visual whenever the words add no topical
   meaning. Text is a liability: only spend it when it carries the concept.

6. In `negative_prompt`, always exclude stray hyphens, letter-spacing artifacts
   and leftover scaffolding from spelled-out text, plus misspelled, truncated,
   duplicated or gibberish lettering and any text in the wrong language."""

IMAGE_PROMPT_SYSTEM = """You design a UNIQUE image concept for a LinkedIn post image.

Every call MUST produce a NEW, distinct visual concept crafted for THIS specific
post — its topic, industry/community and role-based audience. Never recycle a
template, a stock "AI/tech" metaphor, or generic imagery. Do not copy the post
text; create an original visual metaphor for THIS angle.

The image must:
- match the topic AND the field/industry semantics of the post (e.g. if the post
  is about clinic workflows or retail ops, the visual belongs to that world)
- speak to the role-based audience as a sophisticated, in-domain visual
- look premium, professional, suitable for a LinkedIn feed
- avoid excessive text, watermarks, logos, misleading diagrams, unrelated objects

TEXT-IN-IMAGE RULE (critical):
- ANY visible words, labels, headlines, titles, list items, chart/axis labels,
  UI text, banners or speech in the image must be literally ON-TOPIC — they must
  express the post's core concept in a real, meaningful phrase (e.g. the exact
  topic keyword or a short topical tagline), never generic marketing words or
  unrelated wording.
- Every visible word must be written CORRECTLY, completely and in the user's
  chosen language (its real script). No gibberish, no misspelled words, no
  English text when another language is requested, no mixed/wrong scripts.

""" + TEXT_RENDERING_RULES + """

Style guidance: clean premium composition, cinematic lighting, appropriate to
the field (modern workspace, abstract 3D, data-forward editorial, etc.), shallow
depth of field, no people unless the topic is explicitly about people/teams.

Output fields:
- image_prompt: the full detailed positive prompt for the image model — it MUST
  repeat the chosen language and obey the text-in-image rules above
- visual_style: short style descriptor
- composition: framing/composition notes
- negative_prompt: what to avoid — including misspelled/gibberish text, text in
  the wrong language, stray hyphens from spelled-out words, stray unrelated
  words, watermarks, logos

LINKEDIN IMAGE GUIDELINES (authoritative — the concept MUST satisfy every one):
""" + image_rules_text()

IMAGE_PROMPT_HUMAN = """Topic: {topic}
Industry/community: {industry}
Audience: {audience}
Target roles: {audience_roles}
Content angle: {content_angle}
Key concepts: {key_concepts}
User query: {user_query}
Language for any text/graphics in the image: {language}"""

image_prompt_template = ChatPromptTemplate.from_messages(
    [("system", IMAGE_PROMPT_SYSTEM), ("human", IMAGE_PROMPT_HUMAN)]
)

ImagePromptSchema = ImagePromptOutput

# ── Image prompt regeneration (diverse concept) ───────────────
IMAGE_REGEN_SYSTEM = """You are a senior creative art director with 15 years of
experience concepting premium, award-grade imagery for professional social feeds.

Your job: given the topic and the PREVIOUS image concept, design a COMPLETELY
DIFFERENT visual concept. This is a fresh take directed by an experienced
director — never a variation of the previous one:
- a different core metaphor / scene / subject (pick another angle entirely)
- a different composition and color story
- keep it credible in the topic's field/industry and premium enough for a
  LinkedIn feed
- respect the topic's semantics (a clinic workflow post stays in clinical ops,
  a retail post stays in retail) — change the STORY, not the field

Keep the same critical rules:
TEXT-IN-IMAGE RULE (critical):
- Any visible words/labels/headlines must be literally ON-TOPIC, express the
  post's core concept in a real meaningful phrase, be spelled correctly and
  written in the user's chosen language (its real script). No gibberish, no
  wrong-language text.

""" + TEXT_RENDERING_RULES + """

Style: clean premium composition, cinematic lighting, appropriate to the field,
shallow depth of field, no people unless the topic is explicitly about
people/teams.

Output fields:
- image_prompt: the full detailed positive prompt for the image model (repeat
  the chosen language and obey the text-in-image rules above)
- visual_style: short style descriptor
- composition: framing/composition notes
- negative_prompt: what to avoid — including misspelled/gibberish text, wrong-
  language text, stray hyphens from spelled-out words, copying the previous
  concept, watermarks, logos
"""

IMAGE_REGEN_HUMAN = """Topic: {topic}
Industry/community: {industry}
Audience: {audience}
Target roles: {audience_roles}
Content angle: {content_angle}
Key concepts: {key_concepts}
User query: {user_query}
Language for any text/graphics in the image: {language}

Previous concept — design something DIFFERENT from this:
{current_prompt}"""

image_regen_template = ChatPromptTemplate.from_messages(
    [("system", IMAGE_REGEN_SYSTEM), ("human", IMAGE_REGEN_HUMAN)]
)

ImageRegenSchema = ImagePromptOutput

__all__ = [
    "hashtag_prompt",
    "HashtagSchema",
    "TEXT_RENDERING_RULES",
    "image_prompt_template",
    "ImagePromptSchema",
    "image_regen_template",
    "ImageRegenSchema",
]