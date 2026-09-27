# PostCraft — AI LinkedIn content agent

[![CI](https://github.com/mustafaabdullahai-dev/postcraft-linkedin/actions/workflows/ci.yml/badge.svg)](https://github.com/mustafaabdullahai-dev/postcraft-linkedin/actions/workflows/ci.yml)

An **open-source, multi-user LinkedIn AI content generation, review & publishing
platform** built with **FastAPI + LangChain + LangGraph (human-in-the-loop)** on
the backend and **React + Vite + TypeScript + Tailwind** on the frontend.

**Anyone can sign in with their own LinkedIn account**, type a topic, and the
agent drafts a LinkedIn-optimized post + AI image. The author then reviews,
edits and approves it — and it publishes **to their own LinkedIn feed** using
their own OAuth token. Every post is tagged with a **priority** and **post type**
so the library can be filtered (`High/Medium/Low`, `How-To / Thought Leadership /
Insights / News / Motivational / Promotional`, plus lifecycle status). No LinkedIn
app? "Continue as guest" unlocks the full flow in demo mode.

```
┌────────────┐   ┌───────────────┐   ┌────────────┐   ┌───────────────┐   ┌───────────┐
│  React UI  │──▶│  FastAPI API  │──▶│  LangGraph │──▶│ Validator     │──▶│ LinkedIn  │
│  (5173)    │   │  (8001)       │   │  workflow  │   │ (block+LLM)   │   │ publish   │
└────────────┘   └───────────────┘   └────────────┘   └───────────────┘   └───────────┘
      │                │                    │                   │               ▲
  Sign-in          auth/jwt            owner_id            Google Sheets    per-user
  LinkedIn/       @/api/posts        scoping          logging (or dry)    OAuth token
  guest           per-user          session store
```

## Features

- **Multi-user accounts** — **"Sign in with LinkedIn"** behaves like Login-with-
  Google (official OIDC `userinfo` endpoint, `openid/profile/email` scopes, one
  click → consent → back in the app). No credentials? **"Continue as guest"**
  gives a full demo mode with zero setup.
- **Publish as yourself** — publishing uses the *logged-in user's* LinkedIn token
  and URN, never a shared credential. Dry-run returns a simulated `dryrun-…` id.
- **Agentic pipeline** — LangGraph state machine: topic analysis → content plan →
  draft → validate → image → human review → publish, with a `MemorySaver`
  checkpointer and `interrupt()`-based human-in-the-loop approval gate.
- **Calendar + scheduled publishing** — a per-day Calendar view of scheduled and
  published posts, and a background `scheduler` that publishes approved posts at
  their `scheduled_at` time when the server is running.
- **Brand-voice presets** — per-user voice profiles (tone, audience, word target,
  emoji/bullet/story/CTA toggles). Select one in the generator, or create/tune
  your own; a default profile ships so first use "just works".
- **AI editing aids** — one-click **"Suggest edits"** (targeted copy improvements)
  and a **"Suggest & apply"** quality pass that rewrites the draft in place for
  review, plus regenerate (full / text / image) and post duplication.
- **In-place manual editing** — add a **link** or a **block of text** anywhere in
  the draft: place the caret in the post and insert; the panel shows exactly where
  it will land ("inserts after …"). Every insert is markdown-safe.
- **Text-only or text + image** — pick the output in Create (Topic tab). Text-only
  skips both the image-prompt LLM call and the render, so it's faster and cheaper.
- **Manual image upload, with consent** — besides AI generation, a user can attach
  a photo from their own device. Before the browser picker opens they see exactly
  how it is handled (visible only to them, no public access, EXIF/GPS stripped,
  used only for this post). On upload the server re-encodes it (orientation
  applied, metadata removed, resized to 1600px) and it uploads to LinkedIn like
  any other image.
- **LLM image compliance check** — every uploaded image is reviewed by a vision
  model against LinkedIn's image rules and gets a **PASSED / REVIEW** verdict with
  the specific issues (off-topic, watermarks/logos, gibberish or wrong-language
  text, unprofessional or sensitive content), shown right in the Visuals section.
  Configure with `VISION_PROVIDER` (`auto | qwen | gemini | off`).
- **Copy for LinkedIn** — LinkedIn has no markdown renderer, so `**bold**` would
  arrive as literal asterisks. The API strips markdown at the publish boundary and
  the UI offers a **"Copy for LinkedIn"** button that does the same for paste-in.
- **LinkedIn compliance, documented in-app** — the exact posting guidelines the
  agent follows (text, image, safety) are a first-class API surface
  (`GET /api/guidelines`) and a panel in the sidebar/mobile menu, with the
  disclaimer that content is generated in line with LinkedIn's policies.
- **Post filtering** — every post is tagged with `priority` (High/Medium/Low) and
  `post_type` by the planner LLM; filter the library by priority, type, and status.
- **Human-in-the-loop approval** — nothing reaches LinkedIn until the owner
  approves or edits it. Rejected posts are discarded. Published posts can be
  edited again — saving produces a **revision** that republishes a brand-new post.
- **Hybrid validation** — deterministic rule engine (clichés, fabricated metrics,
  emoji cap, hashtag policy, section headers, length) plus an advisory LLM score,
  as a collapsible quality gate with PASSED/FAILED status.
- **Multi-provider LLM layer** — OpenAI-compatible providers behind one interface,
  selected via `TEXT_PROVIDER`: **Groq** (**`openai/gpt-oss-120b`**, default — fast,
  reasoning-capable, strict `json_schema` structured output), Qwen (`qwen-flash`),
  OpenRouter, or a deterministic offline **mock**. `auto` picks the first available.
- **AI image generation** — **Qwen Model Studio** (`wan2.2-t2i-flash`, default —
  ~7s/image via DashScope) with automatic failover to **Gemini Flash Image**
  (native `gemini-3.1-flash-image`, needs Google AI billing) → OpenRouter → an SVG
  mock for keyless demos. Pick the provider with `IMAGE_PROVIDER`.
- **Export** — download the whole library (owner-scoped) as **JSON, CSV or
  Markdown** via `/api/posts/export`.
- **Multilingual** — 100+ language picker (searchable) plus free-text custom
  languages; captions and any in-image text are generated in the chosen language.
- **Structured, approachable UI** — Create / **History** / **Calendar** tabs,
  ⌘K **command palette**, phone/tablet/desktop previews, light/dark/system theme,
  toasts with undo, loading skeletons, a full-screen generating overlay, and a
  one-time "How it works" onboarding guide.
- **Mobile-first navigation** — on phones the account, theme and guidelines
  collapse into a single navbar menu; the busy areas (History toolbar, review
  sections, publish actions) all reflow and keep 44px tap targets.
- **Auditing** — Google Sheets row-per-post per user, plus a local JSONL audit log
  and a per-user JSON post store with full event history.
- **Hardened for public use** — security headers, log redaction, OAuth tokens
  encrypted at rest, rate limiting and daily AI quotas, and a startup check that
  refuses to boot on an insecure production config (see `app/core/config.py`).
- **Resilient** — structured logging with request IDs, publish retry-safe
  endpoint, approval that survives a restart, and dry-run modes everywhere.

## Project layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app: CORS, security headers, rate limit,
│   │   │                           # request-id, docs gating, startup guard, /uploads
│   │   ├── core/                   # config (pydantic-settings), context, structlog
│   │   │                           # (redaction), abuse (rate limit + quotas), crypto
│   │   ├── models/                 # Pydantic schemas, enums, PostRecord + JSON store
│   │   ├── prompts/                # topic/content/image/validation prompts + guidelines
│   │   ├── services/               # llm, image_gen, linkedin, google_sheets, validator,
│   │   │                           # voice profiles, engagement analytics, scheduler
│   │   ├── agents/                 # LangGraph state, nodes, workflow (checkpointer, interrupt)
│   │   └── api/routes/             # auth, posts (generate/review/approve/publish/upload),
│   │                               # voice-profiles, linkedin, health, guidelines
│   ├── tests/                      # 61 pytest tests (nodes, workflow, API, markdown)
│   ├── requirements.txt
│   ├── requirements.lock.txt       # frozen, fully-pinned set
│   ├── requirements-dev.txt        # dev tooling (ruff)
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx                 # dashboard composition + state orchestration
    │   ├── theme.ts                # light/dark/system theme resolution + persistence
    │   ├── services/api.ts         # typed REST client (proxied through Vite)
    │   ├── hooks/                  # useReveal, useMediaQuery
    │   ├── utils/                  # format, linkedin (markdown → LinkedIn plain text)
    │   └── components/             # generator, editor, previews, history, calendar,
    │                               # command palette, mobile menu, guidelines panel…
    ├── vite.config.ts              # dev proxy /api + /uploads → backend
    └── package.json
```

## Quick start

Requires **Python 3.11+** and **Node 18+**.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # paste GROQ, QWEN, GEMINI, LINKEDIN creds as needed

uvicorn app.main:app --reload --port 8001
```

Without any credentials the app runs fully in **mock + dry-run** mode (health endpoint reports the live providers).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5174 (proxies /api + /uploads → :8001)
```

Override with `VITE_DEV_PORT` / `VITE_PROXY_TARGET` if needed.

### 3. Verify

```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/guidelines
curl -X POST http://localhost:8001/api/posts/generate \
     -H 'Content-Type: application/json' \
     -d '{"user_query": "Why Agentic AI is reshaping software engineering"}'
```

**Running providers (both keys optional):**

| Text (`TEXT_PROVIDER`) | Image (`IMAGE_PROVIDER`) |
| --- | --- |
| `groq` — `openai/gpt-oss-120b` (default) | `qwen` — `wan2.2-t2i-flash` (default) |
| `qwen` — `qwen-flash` (DashScope) | `gemini` — `gemini-3.1-flash-image` (needs billing) |
| `openrouter` — any supported model | `openrouter` — e.g. gemini image |
| `mock` — offline demo | `mock` — offline SVG demo |
| `auto` — first available | `auto` — gemini → openrouter → qwen → mock |

## Demo without API keys

`TEXT_PROVIDER=mock IMAGE_PROVIDER=mock uvicorn app.main:app --port 8001` produces realistic
deterministic posts, generates an SVG image, and simulates LinkedIn publish + Sheets logging.
On the login screen click **"Continue as guest (demo)"** — the entire review→approve→publish flow
works out of the box. (If port 8001 is busy, run on another port and start the UI with
`VITE_PROXY_TARGET=http://localhost:<port> npm run dev`.)

## API overview (all JSON, base `/api`)

### Auth

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/auth/linkedin/login` | Redirect to LinkedIn consent (302) |
| `GET` | `/api/auth/linkedin/callback` | OAuth exchange → redirect to frontend with a one-time `code` (+ `session` cookie) |
| `GET` | `/api/auth/session?code=…` | Exchange the OAuth code for a Bearer token (works without cookies) |
| `POST` | `/api/auth/guest` | Start a guest session → `{token, user}` |
| `GET` | `/api/auth/me` | Current user (Bearer token or session cookie) |
| `POST` | `/api/auth/logout` | Clear the session cookie |
| `GET` | `/api/linkedin/status` | Current user's LinkedIn connection status |
| `GET` | `/api/guidelines` | LinkedIn posting guidelines the agent follows (text/image/safety + disclaimer) |

Every `/api/posts/*` endpoint requires auth (Bearer token or session cookie) and is scoped to the signed-in user.

### Posts

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/posts/generate` | Run the agent: `{user_query, include_image}` → full post record |
| `POST` | `/api/posts/batch-generate` | Generate N posts from a topic in one call |
| `GET` | `/api/posts?limit&offset&priority&post_type&status` | List (filtered, owner-scoped) + counts |
| `GET` | `/api/posts/export?format=json|csv|md` | Download the user's whole library |
| `GET` | `/api/posts/{id}` | Get one record (owner only) |
| `PUT` | `/api/posts/{id}` | Edit `final_post` / `hashtags` (owner only) |
| `DELETE` | `/api/posts/{id}` | Delete one record; `DELETE /api/posts` clears all (with filters) |
| `POST` | `/api/posts/{id}/regenerate` | Re-run generation for the post |
| `POST` | `/api/posts/{id}/regenerate-image` | Regenerate just the image |
| `POST` | `/api/posts/{id}/image` | **Upload a manual image** (multipart) — re-encoded, EXIF stripped, owner-only, then vision-reviewed |
| `GET` | `/uploads/{name}` | Serve an uploaded image — **owner only** (401 anonymous, 403 non-owner) |
| `POST` | `/api/posts/{id}/rework` | Rewrite the post to a specified angle |
| `POST` | `/api/posts/{id}/duplicate` | Create a copy as a new draft |
| `POST` | `/api/posts/{id}/suggest-edits` | AI copy-editing suggestions for the draft |
| `POST` | `/api/posts/suggest` | Live editor suggestions for free text |
| `POST` | `/api/posts/{id}/approve` | `{approved: true/false}` — approve (publishes) or reject |
| `POST` | `/api/posts/{id}/publish` | Idempotent publish (retry-safe); 403 if not approved |
| `GET` | `/api/health` | Providers, modes, `linkedin_configured` |

### Voice profiles

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/voice-profiles` | List the user's brand-voice presets |
| `POST` | `/api/voice-profiles` | Create a preset (name, tone, audience, formatting toggles) |
| `PUT` | `/api/voice-profiles/{id}` | Update a preset |
| `DELETE` | `/api/voice-profiles/{id}` | Delete a preset |

**Post lifecycle:** `INITIALIZED → GENERATED → READY_FOR_REVIEW → APPROVED/REJECTED → PUBLISHED (or FAILED)`, with a `SCHEDULED` stage when a publish time is set and the scheduler is running.
Editing a published post puts it back to `EDITED` and republishing creates a fresh LinkedIn post (a revision), keeping the original.

**Uploaded images** are owner-scoped twice over: the upload endpoint requires you to
own the post, and `/uploads/{name}` returns `401` when anonymous and `403` for any
user who doesn't own the post the image belongs to. Each upload also carries its
vision review in `record.image_analysis` (`{status, score, issues, summary, model,
checked_at}`). The frontend loads these images with the session token via
`AuthedImage`, so token-based (guest) sessions work too.
**Filters:** `priority` (`High`/`Medium`/`Low`), `post_type` (`How-To`, `Thought Leadership`, `Insights`,
`News`, `Motivational`, `Promotional`), `status` (lifecycle value, e.g. `PUBLISHED`).

## LinkedIn OAuth (per-user login + real publishing)

**"Sign in with LinkedIn" works exactly like Google Login** — one click takes the
user to LinkedIn's consent screen, and they land back inside the app. Like any
OAuth login, it needs a one-time developer app:

1. Create an app at <https://www.linkedin.com/developers/apps> and add the
   **"Sign In with LinkedIn using OpenID Connect"** product (scopes `openid`,
   `profile`, `email`) and, to enable publishing, the **"Share on LinkedIn"**
   product (scope `w_member_social`).
2. Add `http://localhost:8001/api/auth/linkedin/callback` as an **Authorized
   redirect URL** (or `http://localhost:5174/api/auth/linkedin/callback` behind
   the Vite proxy) — for a tunnel/deployment use the exact public
   `{FRONTEND_URL}/api/auth/linkedin/callback`.
3. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_DRY_RUN=false`
   in `.env` and restart — the login screen activates the blue button for every
   visitor.
4. Identity comes from LinkedIn's OIDC `userinfo` endpoint (`sub/name/picture/
   email`); each account stores its own token + URN and publishes to **that
   user's** LinkedIn feed (green "connected" dot in the header). Tokens carry
   LinkedIn's `refresh_token` for automatic refresh.

## LinkedIn guidelines & validation

The rules the agent follows are the single source of truth in
`backend/app/prompts/guidelines.py`; the writer, image-prompt and validator
prompts all receive them, `GET /api/guidelines` serves them, and the app shows
them (with a "we follow LinkedIn's policies" disclaimer) in the sidebar and the
mobile menu.

**Blocking rules (decided in code, never by the model):**

- Length between 300 and 3000 characters (LinkedIn's limit).
- 5–10 hashtags, all topic/niche-relevant — **no fixed or personal tags**; Latin/
  Arabic scripts keep the post's language, CJK falls back to English (LinkedIn
  cannot index CJK hashtags). `clean_post` removes label/tag-only lines and
  appends one clean tag line.
- No literal section headers, no code fences, no stray `Hashtags:` label.
- Emoji budget: max 12, and never starting a line.
- No fabricated metrics/percentages, no AI clichés ("game-changer", "delve", …).
- **No engagement bait** ("like if you agree", "comment YES", "tag a friend",
  "follow for more", "share this if…") — LinkedIn discourages it.

An optional second pass asks the LLM for a **quality score** and subjective
suggestions (advisory only — it never blocks).

**Publishing boundary:** LinkedIn renders `shareCommentary.text` as plain text, so
`to_plain_text()` strips markdown (`**bold**`, `~~strike~~`, `#`/`>`/list markers)
right before the API call — while the stored post and the CSV/Markdown exports
keep their markdown. The frontend mirrors this in `utils/linkedin.ts` for the
"Copy for LinkedIn" button.

## Google Sheets logging (production)

1. Create a Google Cloud service account JSON → `GOOGLE_SERVICE_ACCOUNT_JSON` (paste JSON or use `file:./creds.json`).
2. Share a spreadsheet with the service-account email; put its ID in `GOOGLE_SHEET_ID`.
3. Set `GOOGLE_SHEETS_DRY_RUN=false`. Rows are appended per post with topic, draft, final copy,
   hashtags, image URL, statuses, and timestamps.

With `GOOGLE_SHEETS_DRY_RUN=true` (default) every event still lands in `backend/data/audit.jsonl`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q     # 61 tests, runs offline (mock providers)
.venv/bin/ruff check app tests                  # lint (same rule set as CI)
```

CI (`.github/workflows/ci.yml`) runs both jobs on every push/PR:
backend **ruff lint + pytest** and frontend **typecheck + build** (`tsc && vite build`).

## Production notes

- JSON-file stores (posts, users, voices, usage) and the in-memory LangGraph
  checkpointer suit a single node; move to Postgres/Redis before scaling
  horizontally.
- Manually uploaded images live in `backend/data/uploads/` and are served through
  the authenticated `/uploads` endpoint — never as public static files.
- `frontend/vite.config.ts` proxies `/api` and `/uploads` to `:8001`
  (`VITE_PROXY_TARGET` to override). In production serve `frontend/dist` from
  FastAPI or nginx and proxy those two paths.
- Always set `ENVIRONMENT=production` in a real deployment and read
  `backend/app/core/config.py` for the supported settings.
- **Never commit `.env` or `backend/data/`** — they hold credentials, user records,
  posts and uploads.