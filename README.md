# PostCraft — AI LinkedIn content agent

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
- **Post filtering** — every post is tagged with `priority` (High/Medium/Low) and
  `post_type` by the planner LLM; filter the library by priority, type, and status.
- **Human-in-the-loop approval** — nothing reaches LinkedIn until the owner
  approves or edits it. Rejected posts are discarded. Published posts can be
  edited again — saving produces a **revision** that republishes a brand-new post.
- **Hybrid validation** — deterministic rule engine (clichés, fabricated metrics,
  emoji cap, hashtag policy, section headers, length) plus an advisory LLM score,
  with one-click "Suggest & apply" that rewrites the draft in place for review.
- **Multi-provider LLM layer** — OpenAI-compatible providers (Qwen/Model Studio
  default), or a deterministic offline **mock** provider.
- **AI image generation** — **Gemini Flash Image** (via OpenRouter) as primary
  with automatic failover to **Qwen Model Studio** (`wan2.1-t2i-turbo`), then an
  SVG mock fallback for keyless demos.
- **Multilingual** — 100+ language picker (searchable) plus free-text custom
  languages; captions and any in-image text are generated in the chosen language.
- **Structured, approachable UI** — 4-step review flow (Review & edit → Visual →
  Quality gate → Hashtags & publish), Create/History tabs, phone/tablet/desktop
  previews, light/dark/system theme, toasts, and an onboarding guide.
- **Auditing** — Google Sheets row-per-post per user, plus a local JSONL audit log
  and a per-user JSON post store with full event history.
- **Resilient** — rate limited API (configurable), structured logging with request
  IDs, publish retry-safe endpoint, and dry-run modes everywhere.

## Project layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app: CORS, rate limit, request-id, lifespan
│   │   ├── core/                   # config (pydantic-settings), context, structlog setup
│   │   ├── models/                 # Pydantic schemas, enums, PostRecord + JSON store
│   │   ├── prompts/                # topic/content/image/validation prompt templates
│   │   ├── services/               # llm, image_gen, linkedin, google_sheets, validator
│   │   ├── agents/                 # LangGraph state, nodes, workflow (checkpointer, interrupt)
│   │   └── api/routes/             # posts (generate/review/approve/publish), linkedin, health
│   ├── tests/                      # 23 pytest tests (nodes, workflow, full API flow)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx                 # dashboard composition + state orchestration
    │   ├── theme.ts                # light/dark/system theme resolution + persistence
    │   ├── services/api.ts         # typed REST client (proxied through Vite)
    │   └── components/             # generator, previews, editor, approval, history, toggle…
    ├── vite.config.ts              # dev proxy /api → http://localhost:8000
    └── package.json
```

## Quick start

Requires **Python 3.11+** and **Node 18+**.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # optionally paste OPENROUTER/GEMINI, QWEN, LINKEDIN creds

uvicorn app.main:app --reload --port 8000
```

Without any credentials the app runs fully in **mock + dry-run** mode (health endpoint reports the live providers).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api → :8000)
```

### 3. Verify

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/posts/generate \
     -H 'Content-Type: application/json' \
     -d '{"user_query": "Why Agentic AI is reshaping software engineering"}'
```

## Demo without API keys

`TEXT_PROVIDER=mock IMAGE_PROVIDER=mock uvicorn app.main:app --port 8000` produces realistic
deterministic posts, generates an SVG image, and simulates LinkedIn publish + Sheets logging.
On the login screen click **"Continue as guest (demo)"** — the entire review→approve→publish flow
works out of the box. (If port 8000 is busy, run on 8001 and start the UI with
`VITE_PROXY_TARGET=http://localhost:8001 npm run dev`.)

## API overview (all JSON, base `/api`)

### Auth

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/auth/linkedin/login` | Redirect to LinkedIn consent (302) |
| `GET` | `/api/auth/linkedin/callback` | OAuth exchange → sets `session` cookie → redirect to frontend |
| `POST` | `/api/auth/guest` | Start a guest session → `{token, user}` |
| `GET` | `/api/auth/me` | Current user (Bearer token or session cookie) |
| `POST` | `/api/auth/logout` | Clear the session cookie |
| `GET` | `/api/linkedin/status` | Current user's LinkedIn connection status |

Every `/api/posts/*` endpoint requires auth and is scoped to the signed-in user.

### Posts

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/posts/generate` | Run the agent: `{user_query}` → full post record |
| `GET` | `/api/posts?limit&offset&priority&post_type&status` | List (filtered, owner-scoped) + counts |
| `GET` | `/api/posts/{id}` | Get one record (owner only) |
| `PUT` | `/api/posts/{id}` | Edit `final_post` / `hashtags` (owner only) |
| `POST` | `/api/posts/{id}/regenerate` | Re-run generation for the post |
| `POST` | `/api/posts/{id}/regenerate-image` | Regenerate just the image |
| `POST` | `/api/posts/{id}/approve` | `{approved: true/false}` — approve (publishes) or reject |
| `POST` | `/api/posts/{id}/publish` | Idempotent publish (retry-safe); 403 if not approved |
| `GET` | `/api/health` | Providers, modes, `linkedin_configured` |

**Post lifecycle:** `INITIALIZED → GENERATED → READY_FOR_REVIEW → APPROVED/REJECTED → PUBLISHED (or FAILED)`.
Editing a published post puts it back to `EDITED` and republishing creates a fresh LinkedIn post (a revision), keeping the original.
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
2. Add `http://localhost:8000/api/auth/linkedin/callback` as an **Authorized
   redirect URL** (or `http://localhost:5173/api/auth/linkedin/callback` behind
   the Vite proxy).
3. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_DRY_RUN=false`
   in `.env` and restart — the login screen activates the blue button for every
   visitor.
4. Identity comes from LinkedIn's OIDC `userinfo` endpoint (`sub/name/picture/
   email`); each account stores its own token + URN and publishes to **that
   user's** LinkedIn feed (green "connected" dot in the header). Tokens carry
   LinkedIn's `refresh_token` for automatic refresh.

## Validation rules (blocking)

- Length between 300 and 3000 characters.
- 5–10 hashtags, `#GenAIWithAM` always first, no repeated tags.
- No literal section headers (`**`/headings), no fabricated metrics or percentages.
- Max 12 emojis, no emoji leading a line, no overused clichés ("game-changer", "unlocking the power"…).
- No stray `Hashtags:` label — a `clean_post` node strips label lines and tag-only lines anywhere, then appends one clean hashtag line.

An optional second pass asks the LLM for a **quality score** and subjective suggestions (advisory only — it never blocks).

## Google Sheets logging (production)

1. Create a Google Cloud service account JSON → `GOOGLE_SERVICE_ACCOUNT_JSON` (paste JSON or use `file:./creds.json`).
2. Share a spreadsheet with the service-account email; put its ID in `GOOGLE_SHEET_ID`.
3. Set `GOOGLE_SHEETS_DRY_RUN=false`. Rows are appended per post with topic, draft, final copy,
   hashtags, image URL, statuses, and timestamps.

With `GOOGLE_SHEETS_DRY_RUN=true` (default) every event still lands in `backend/data/audit.jsonl`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q     # 23 tests, runs offline (mock providers)
```

## Production notes

- The LangGraph checkpointer is **in-memory** (`MemorySaver`): restarting the server loses in-flight
  approval threads. Swap in `SqliteSaver`/`PostgresSaver` for horizontal deployments.
- Posts and users are JSON-file stores; swap `PostStore`/`UserStore` for Postgres/Redis for scale.
- `frontend/vite.config.ts` proxies `/api` to `:8000` by default (`VITE_PROXY_TARGET` to override,
  e.g. `http://localhost:8001` when 8000 is busy); in production serve the built `frontend/dist`
  from FastAPI (or via nginx to `/api`).
- Set `SECRET_KEY` to a long random value in production (it signs session tokens).
- Never commit `.env`; keep `backend/data/` gitignored (posts, users, audit logs are local state).