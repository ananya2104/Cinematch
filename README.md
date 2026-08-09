# CineMatch — conversational movie recommendation chatbot

A polished, multilingual chat assistant that has a short conversation with the user (mood/genre,
duration, optional actor/director/industry, streaming platforms) and then recommends real movies
with a direct "watch now" link and real IMDb rating, using Azure OpenAI for the conversation and
TMDB + Watchmode for movie data and streaming availability. The user can keep asking for more
picks or refine their preferences indefinitely — platforms are only ever asked about once per
session, and the whole UI (not just the chat replies) switches language instantly when the user
picks one from the top bar.

## Stack

- **Backend**: FastAPI (Python 3.12), served with Uvicorn
- **Frontend**: Server-rendered Jinja2 template + vanilla JS/CSS — no build step, with a small
  client-side i18n dictionary for the static chrome (`app/static/js/app.js`)
- **LLM**: Azure OpenAI Responses API (`client.responses.create`, structured JSON output)
- **Movie data**: [TMDB API](https://www.themoviedb.org/documentation/api)
- **Streaming availability**: TMDB `watch/providers` (primary) + [Watchmode](https://api.watchmode.com/) (deep links)
- **Ratings**: real IMDb rating via [OMDb API](https://www.omdbapi.com/) (optional — degrades to no
  rating badge if `OMDB_API_KEY` isn't set)
- **Session memory**: in-memory by default; set `REDIS_URL` to switch to a Redis-backed store that
  survives restarts and works correctly across multiple app instances (see `app/session_store.py`)

## Project layout

```
app/
  main.py            FastAPI app + routes (/, /api/chat, /api/platforms)
  config.py           Settings loaded from .env
  session_store.py     In-memory session store (conversation history + extracted slots)
  llm.py                 Azure OpenAI wrapper: dialogue turns + movie suggestion + blurbs
  tmdb.py                 TMDB client (search a suggested title, watch providers)
  watchmode.py             Watchmode client (deep links to the exact platform)
  omdb.py                   OMDb client (real IMDb rating by IMDb id)
  recommender.py             Verifies the LLM's picks are real + available, enriches them
  http_client.py             Shared GET-JSON helper (httpx, with a curl fallback — see note below)
  models.py                   Pydantic request/response/session models
  templates/index.html         Chat UI markup (Jinja2 — used when this app serves its own frontend)
  static/css/style.css          Dark theme, matches the provided design reference
  static/js/app.js               Chat logic, session persistence, rendering
docs/                             Static export of the frontend, for hosting separately (e.g. GitHub
                                  Pages) from the backend — see "Split hosting" below. Same app.js/
                                  style.css as app/static/, kept in sync manually; index.html is a
                                  de-templated copy that points at the deployed backend's URL.
```

## Local setup

1. **Create/activate the virtual environment** (already created at `venv/` if you're continuing this
   session — otherwise):
   ```
   python -m venv venv
   ```
   Windows: `venv\Scripts\activate` · macOS/Linux: `source venv/bin/activate`

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Configure secrets** — copy `.env.example` to `.env` and fill in:
   - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
   - `TMDB_READ_ACCESS_TOKEN`
   - `WATCHMODE_API_KEY`
   - `OMDB_API_KEY` (optional) — get a free key at https://www.omdbapi.com/apikey.aspx (instant
     email confirmation) to show the real IMDb rating on each recommendation card. Without it the
     app runs fine, it just skips the rating badge.

   > **Rotate your keys.** The Azure OpenAI, TMDB, and Watchmode keys used to build this were
   > pasted into a chat session, which should be treated as exposed. Generate fresh ones in the
   > Azure AI Foundry portal / TMDB account settings / Watchmode dashboard before using this app
   > for anything beyond local testing, and never commit `.env`.

4. **Run it**:
   ```
   uvicorn app.main:app --reload
   ```
   Open http://127.0.0.1:8000.

## How the conversation works

1. The user picks a language from the top bar (or leaves it on "Auto" and just types in whatever
   language they like). Picking a language re-translates the entire visible UI immediately — empty
   state, quick-reply chips, the platform checklist, "Watch now", everything — via the `I18N` table
   in `app/static/js/app.js`. It also **pins** the assistant's replies to that language for the rest
   of the session, overriding auto-detection of whatever language the user happens to type in
   (`ui_language` in the request always wins — see `_language_instruction` in `app/llm.py`). The user
   can change the language again mid-conversation at any time.
2. Each turn, `app/llm.py` asks Azure OpenAI for a structured JSON response containing: a short
   reply (in the right language), any newly-extracted preferences (mood, genre, duration, industry,
   who they're watching with, new-vs-classic, a rating bar, actor/director, platforms), whether
   enough is known to recommend, and 2–4 quick-reply chips. Extraction is a **delta, not a recap** —
   the prompt explicitly tells the model to only fill in what the latest message actually changes and
   leave everything else null, and `_merge_slots` in `app/main.py` layers that onto what's already
   known. (Earlier versions had the model echo back everything it already knew on every turn, which
   silently overwrote genuine changes with stale values — see the "actor/director pivot" note below.)
3. **The very first question establishes the "basis"** — how this round of picks should be chosen:
   by genre/mood, around a specific actor/director/franchise, around a release era/decade, or around
   an occasion/persona (date night, family time, solo unwind, ...). If the user's opening message
   already makes this obvious ("give me some Nolan movies" → actor/director; "90s action movies" →
   era), the model infers it silently and skips straight to that branch instead of asking. Each basis
   then drives its own compulsory checklist (`Slots.basis`, `_SYSTEM_PROMPT` in `app/llm.py`):
   - **genre_mood** (the default/general path): mood, genre, duration, company, new-vs-classic.
   - **person_or_franchise**: the actor/director/franchise name (if not already given), duration,
     company — genre and recency are optional bonus only, since the person/franchise already narrows
     things down.
   - **release_era**: the specific decade/era, genre, duration, company — no separate new-vs-classic
     question, since the era already answers that.
   - **persona**: who/the occasion (reuses the `company` field), mood, genre, duration.

   Once `basis` is set it's kept for the rest of the conversation (it never flips mid-session), and
   the model never asks more than `llm.MAX_CLARIFYING_TURNS` (6) questions total, including the
   opening basis question — vague answers or phrases like "surprise me" skip straight to
   recommending with sensible defaults filled in.
4. Before the first recommendation, the platform-selection checklist widget appears — **exactly
   once per session** (tracked via `SessionState.platforms_resolved`, not just "is the list
   non-empty", so skipping still counts as resolved). It never reappears after that, even if the
   user asks for more picks or changes their mind about genre.
5. **The LLM picks the actual movies**, from its own real knowledge — `llm.suggest_movies` (in
   `app/llm.py`) turns the collected slots into a plain-language brief (mood, genre, duration,
   industry, company, recency, rating bar, actor/director/franchise, and which platforms the user
   has) and asks for a generous shortlist (10, ranked best-first) of real, specific titles + release
   year + a tailored one-line blurb each — not a database query, an actual curator call. `app/
   recommender.py` then verifies each suggestion for real: looks it up on TMDB (`search_movie`) to
   get its real id/poster/rating, checks TMDB's `watch/providers` to confirm it's genuinely
   streaming on one of the user's selected platforms, and resolves a real deep link (Watchmode,
   falling back to TMDB's own link) plus a real IMDb rating (via OMDb). Only survivors get shown —
   anything the model got wrong, or that isn't actually available, is silently dropped rather than
   shown broken. If fewer than 4 survive, a second round asks the model again with the failed
   titles excluded and explicit instructions to prioritize availability over an exact match (being
   honest about it in the intro if it has to relax something, e.g. a director whose films don't
   suit the mood — see the Nolan example below). This is slower than a plain database filter (each
   candidate costs a handful of API calls to verify), but the picks are noticeably more specific and
   context-aware than an algorithmic query can produce — e.g. asking for "Nolan movies" after
   setting up a "funny" mood earlier gets a real reply like *"Nolan rarely makes outright comedies,
   but these picks foreground his sharpest banter and darkest wit..."* rather than either a rigid
   empty result or four random unrelated films.
6. **Once the first batch of recommendations has been shown, every further message is either "more
   of these" or a refinement** ("actually, something scarier", "give me some Nolan movies") rather
   than restarting the intake questions — gated by `SessionState.recommended` + the model's own
   `wants_recommendations` signal in `app/main.py`, so a genuine follow-up question ("what's the
   second one about?") gets an answer instead of an unwanted new batch. Movies and titles already
   shown are tracked (`SessionState.recommended_ids` / `recommended_titles`) and excluded from every
   later batch, so "show more" never repeats — verified across multiple rounds of "give me more
   Nolan movies" with zero duplicates.
7. The frontend keeps the full transcript in `localStorage` (keyed to a `session_id` also stored
   there), so a page refresh restores the conversation instantly without re-hitting the backend; the
   backend's own session store keeps the actual conversation state for as long as the process runs
   (trimmed to the most recent 60 messages so a very long chat can't grow it unbounded). Concurrent
   requests for the same session are serialized with a per-session lock (`SessionStore.session_lock`)
   so they can't race and clobber each other's state. The model only ever sees its own real,
   already-generated blurbs in the conversation history (not just a one-line intro), so a follow-up
   question about a specific recommended movie is grounded in what was actually shown rather than the
   model's unrelated background knowledge about a different film with the same title.

## A note on networking / `http_client.py`

While building this, requests from Python (both `httpx` and `curl_cffi`) to `api.themoviedb.org` and
`api.watchmode.com` were being reset mid-TLS-handshake on the dev network, while `curl` (which uses a
different TLS stack) went through fine. `app/http_client.py` therefore tries `httpx` first and
transparently falls back to shelling out to `curl` on a transport error, with retries. This is
harmless and likely unnecessary on Azure (a clean network), but keeps the app resilient if a similar
network/AV interference shows up elsewhere.

## Known MVP limitations, and how to level them up

- **Session storage defaults to in-memory** (`InMemorySessionStore`) unless `REDIS_URL` is set, in
  which case `RedisSessionStore` (same file) takes over automatically — conversation state then
  survives restarts/redeploys and is correct across multiple app instances, since it's no longer
  sitting in one process's RAM. Both implement the same `SessionStore` interface, so nothing else in
  the app changes based on which one is active. To use it: run a local Redis for dev
  (`docker run -p 6379:6379 redis`, then `REDIS_URL=redis://localhost:6379/0`) or provision Azure
  Cache for Redis and put its connection string in `REDIS_URL` — Basic tier is enough for this
  workload and is the standard pairing for an App Service that needs shared state. If Redis is
  configured but unreachable at startup, the app logs a warning and falls back to in-memory rather
  than failing to boot.
  - Note: the bugs reported earlier (stale filters bleeding into a new actor/director request,
    "show more" running out early, "Marvel movies" returning unrelated films) were dialogue/query
    logic bugs, not a session-memory problem — the conversation *was* being remembered, just merged
    and queried incorrectly. Those are now fixed (see the "how the conversation works" section
    above); Redis is a separate, genuinely-useful upgrade for surviving restarts/scaling, not a fix
    for those specific issues.
  - If you also want conversations to persist for a *returning* user across days/devices (not just
    "don't lose it mid-conversation"), that's a different, bigger step: real accounts (Azure AD B2C
    or simple email/password) plus a proper database (Postgres/Cosmos DB) instead of — or alongside —
    Redis, since Redis here is meant for hot/ephemeral state, not permanent history.
- **Why not LangGraph (or a similar agent framework):** the actual problems so far — stale slots
  overriding a fresh request, pagination logic, keyword search — were bugs in this app's own Python
  logic and prompt wording, not something a graph-orchestration framework fixes by itself; adding one
  would mean a real rewrite (multiple LLM calls per turn instead of one, a new dependency, a new
  mental model) in exchange for structure this app doesn't yet need — one deployable, one dialogue
  policy, one recommendation step. It's worth reconsidering if the flow grows real branching
  complexity (e.g. tool-calling out to multiple different agents, long-running multi-step tasks with
  retries/checkpointing) — worth flagging if you want that.
- **Streaming catalog is curated to India (`STREAMING_REGION=IN`)** and to six platforms that
  actually exist in TMDB's India catalog today (Disney+ Hotstar and JioCinema merged into
  "JioHotstar" in 2025, so that's what's offered instead of the two separate services).
- **Other things worth adding for a more "seamless, professional" feel, roughly in order of value:**
  1. *Streaming response* — the reply currently arrives all at once after the model finishes; wiring
     up SSE/streaming (the Responses API supports it) would make replies feel instant rather than
     waiting a beat, especially for the two-call recommendation flow.
  2. *A visible "typing" state per phase* — right now it's one generic typing indicator; distinguishing
     "thinking" vs "checking what's available on your platforms" sets better expectations during the
     multi-second recommendation build.
  3. *Basic rate limiting / abuse protection* on `/api/chat` before this is public — nothing currently
     stops a script from hammering it and burning through the Azure OpenAI/TMDB/OMDb quotas.
  4. *Structured logging/telemetry* (Azure Application Insights) instead of the current basic Python
     logger, so you can see real usage patterns and error rates once this has real users.

## Split hosting: backend on Azure, frontend on GitHub Pages

This is the current setup: the API runs on Azure App Service, and the static frontend
(`docs/` in this repo) is served by GitHub Pages from the same repo. They talk to each other over
CORS — `app/config.py`'s `CORS_ALLOWED_ORIGINS` on the backend, and `window.__API_BASE__` in
`docs/index.html` on the frontend, are the two ends of that connection. Everything below is done in
the Azure Portal (no CLI needed).

### Part 1 — Backend on Azure App Service

1. Go to [portal.azure.com](https://portal.azure.com) → **Create a resource** → **Web App**.
2. **Basics tab**:
   - Resource Group: create new, e.g. `cinematch-rg`
   - Name: `cinematch-hb-api` — **use this exact name if it's available**, since `docs/index.html`
     is already pointing at `https://cinematch-hb-api.azurewebsites.net`. If it's taken (App Service
     names are globally unique), pick another name and note it — you'll need to update one line
     later (see Part 3).
   - Publish: **Code**
   - Runtime stack: **Python 3.12**
   - Operating System: **Linux**
   - Region: pick whatever's closest to you (e.g. Central India)
   - Pricing plan: create a new App Service Plan, SKU **Basic B1**
3. **Review + create** → **Create**. Wait for deployment to finish, then **Go to resource**.
4. **Deployment Center** (left sidebar) → Source: **GitHub** → authorize/sign in to GitHub if
   prompted → Organization: your GitHub username → Repository: `CineMatch` → Branch: `main` → Save.
   This creates a GitHub Actions workflow in your repo that redeploys the backend on every push.
5. **Configuration** (left sidebar) → **General settings** tab:
   - Startup Command:
     ```
     gunicorn -k uvicorn.workers.UvicornWorker -w 2 app.main:app
     ```
   - Always On: **On** (this is what stops the in-memory session store from being recycled between
     requests — only available on Basic tier and above, which is why B1 rather than the free tier)
   - Save (this restarts the app)
6. Still in **Configuration** → **Application settings** tab → **New application setting** for each
   of these (values from your local `.env`), then **Save**:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_DEPLOYMENT`
   - `TMDB_READ_ACCESS_TOKEN`
   - `WATCHMODE_API_KEY`
   - `OMDB_API_KEY` (optional, for the IMDb rating badge)
   - `STREAMING_REGION` = `IN`
   - `CORS_ALLOWED_ORIGINS` = `https://<your-github-username>.github.io`
     (no trailing slash or path — just the origin)
7. Wait for the GitHub Actions deploy from step 4 to finish (check the **Actions** tab on your
   GitHub repo, or the Deployment Center's log). Once it's green, visit
   `https://cinematch-hb-api.azurewebsites.net/` — you should see the same chat UI, confirming the
   backend is live and can serve itself too (that route stays working as a fallback/health check
   even though the frontend now normally comes from GitHub Pages).

### Part 2 — Frontend on GitHub Pages

1. On your GitHub repo → **Settings** → **Pages** (left sidebar).
2. Source: **Deploy from a branch** → Branch: `main`, folder: **`/docs`** → **Save**.
3. Wait about a minute; GitHub will show the live URL —
   `https://<your-github-username>.github.io/CineMatch/`.
4. Open it and run through a full conversation. This is the real end-to-end test: the page is on
   `github.io`, calling the API on `azurewebsites.net` — if you see a CORS error in the browser
   console, double check `CORS_ALLOWED_ORIGINS` in Part 1 step 6 matches your `github.io` origin
   exactly.

### Part 3 — If the Azure app name wasn't available

Edit `docs/index.html` and change the one line near the bottom:
```html
window.__API_BASE__ = "https://<your-actual-app-name>.azurewebsites.net";
```
then commit and push — GitHub Pages picks up the change automatically.

### Local development still works unchanged

`app/templates/index.html` + `app/static/` (served by FastAPI itself via Jinja2) is untouched — run
`uvicorn app.main:app --reload` and everything works exactly as before, same-origin, no CORS
involved. The `docs/` folder is only used once you deploy the frontend separately.
