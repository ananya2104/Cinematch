from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import llm, recommender
from app.config import get_settings
from app.models import ChatMessage, ChatRequest, ChatResponse, PlatformsRequest
from app.session_store import InMemorySessionStore, RedisSessionStore, SessionStore

logger = logging.getLogger("cinematch")

APP_DIR = Path(__file__).parent
app = FastAPI(title="CineMatch")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


def _build_session_store() -> SessionStore:
    settings = get_settings()
    if settings.redis_url:
        try:
            store = RedisSessionStore(settings.redis_url, ttl_minutes=settings.session_ttl_minutes)
            store._client.ping()
            logger.info("Using Redis-backed session store")
            return store
        except Exception:
            logger.exception("REDIS_URL is set but Redis is unreachable — falling back to in-memory sessions")
    return InMemorySessionStore(ttl_minutes=settings.session_ttl_minutes)


_store = _build_session_store()

LANGUAGE_OPTIONS = [
    {"code": "en", "label": "English"},
    {"code": "hi", "label": "हिंदी"},
    {"code": "es", "label": "Español"},
    {"code": "ta", "label": "தமிழ்"},
    {"code": "bn", "label": "বাংলা"},
    {"code": "fr", "label": "Français"},
]

POST_RECOMMEND_REPLIES = {
    "en": ["Show me more", "Something different"],
    "hi": ["और दिखाओ", "कुछ अलग चाहिए"],
    "es": ["Muéstrame más", "Algo diferente"],
    "ta": ["இன்னும் காட்டு", "வேறு ஏதாவது"],
    "bn": ["আরও দেখাও", "অন্য কিছু চাই"],
    "fr": ["Montre-m'en plus", "Autre chose"],
}


def _post_recommend_quick_replies(language: str) -> list[str]:
    return POST_RECOMMEND_REPLIES.get(language, POST_RECOMMEND_REPLIES["en"])


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "languages": LANGUAGE_OPTIONS,
            "platforms": recommender.available_platform_names(),
        },
    )


def _merge_slots(session, result) -> None:
    slots = session.slots

    # A newly-named actor, director, or topic/franchise ("give me some Nolan
    # movies", "something Marvel") is a hard pivot that should override whatever
    # mood/genre/duration/industry was said earlier — otherwise a stale "short
    # comedy" filter combines with "directed by Nolan" and returns nothing, since
    # none of his films fit that. It also supersedes any *other* specific request
    # from earlier (a new topic drops an old actor/director and vice versa). Only
    # clear a field if this same message doesn't also re-specify it.
    new_actor = bool(result.actor) and result.actor != slots.actor
    new_director = bool(result.director) and result.director != slots.director
    new_topic = bool(result.topic) and result.topic != slots.topic
    if new_actor or new_director or new_topic:
        if not result.genres:
            slots.genres = []
        if not result.duration_max_minutes:
            slots.duration_max_minutes = None
        if not result.industry:
            slots.industry = None
        if not result.recency:
            slots.recency = None
        if not result.era:
            slots.era = None
        if not result.min_rating:
            slots.min_rating = None
        if new_actor and not result.director:
            slots.director = None
        if new_director and not result.actor:
            slots.actor = None
        if (new_actor or new_director) and not result.topic:
            slots.topic = None
        if new_topic:
            if not result.actor:
                slots.actor = None
            if not result.director:
                slots.director = None

    if result.basis and not slots.basis:
        # The basis (how to pick movies) is decided once at the start of a conversation
        # and shouldn't flip later just because the model happened to echo it again.
        slots.basis = result.basis
    if result.mood:
        slots.mood = result.mood
    if result.genres:
        # Treat newly-mentioned genres as a replacement, not an addition — lets the user
        # say "actually, something scarier" after the fact and have it stick.
        slots.genres = list(dict.fromkeys(result.genres))
    if result.duration_max_minutes:
        slots.duration_max_minutes = result.duration_max_minutes
    if result.industry:
        slots.industry = result.industry
    if result.company:
        slots.company = result.company
    if result.recency:
        slots.recency = result.recency
    if result.era:
        slots.era = result.era
    if result.min_rating:
        slots.min_rating = result.min_rating
    if result.topic:
        slots.topic = result.topic
    if result.actor:
        slots.actor = result.actor
    if result.director:
        slots.director = result.director
    if result.platforms_mentioned:
        matched = recommender.match_catalog_platforms(result.platforms_mentioned)
        for name in matched:
            if name not in slots.platforms:
                slots.platforms.append(name)
        if matched:
            session.platforms_resolved = True


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    with _store.session_lock(payload.session_id):
        return _chat_impl(payload)


def _chat_impl(payload: ChatRequest) -> ChatResponse:
    session = _store.get(payload.session_id)
    session.history.append(ChatMessage(role="user", content=payload.message))
    session.turn_count += 1

    try:
        result = llm.run_dialogue_turn(session, payload.message, payload.ui_language)
    except Exception:
        logger.exception("dialogue turn failed")
        reply = "Sorry, I hit a snag understanding that — could you try rephrasing?"
        session.history.append(ChatMessage(role="assistant", content=reply))
        _store.save(session)
        return ChatResponse(session_id=session.session_id, reply_text=reply, language=session.language)

    _merge_slots(session, result)
    session.language = payload.ui_language or result.detected_language or session.language

    # Once we've recommended at least once, never restart the intake questions or
    # re-ask for platforms. But not every message afterward wants a new batch of
    # movies — only regenerate when the model reads the message as actually asking
    # for one ("more", "something different", a changed preference); otherwise just
    # reply conversationally (a question, a comment, etc.) so it doesn't feel like
    # the bot ignores what was actually said.
    if session.recommended:
        if result.wants_recommendations:
            reply_text, recommendations = _run_recommendations(session)
            return ChatResponse(
                session_id=session.session_id,
                reply_text=reply_text,
                quick_replies=_post_recommend_quick_replies(session.language),
                selected_platforms=session.slots.platforms,
                recommendations=recommendations,
                language=session.language,
            )
        reply_text = result.reply_text
        session.history.append(ChatMessage(role="assistant", content=reply_text))
        _store.save(session)
        return ChatResponse(
            session_id=session.session_id,
            reply_text=reply_text,
            quick_replies=result.quick_replies or _post_recommend_quick_replies(session.language),
            selected_platforms=session.slots.platforms,
            language=session.language,
        )

    ready = result.ready_to_recommend or session.turn_count >= llm.MAX_CLARIFYING_TURNS

    if ready and not session.platforms_resolved:
        reply_text = result.reply_text
        session.history.append(ChatMessage(role="assistant", content=reply_text))
        _store.save(session)
        return ChatResponse(
            session_id=session.session_id,
            reply_text=reply_text,
            needs_platform_selection=True,
            available_platforms=recommender.available_platform_names(),
            selected_platforms=session.slots.platforms,
            language=session.language,
        )

    if ready and session.platforms_resolved:
        reply_text, recommendations = _run_recommendations(session)
        return ChatResponse(
            session_id=session.session_id,
            reply_text=reply_text,
            quick_replies=_post_recommend_quick_replies(session.language),
            selected_platforms=session.slots.platforms,
            recommendations=recommendations,
            language=session.language,
        )

    reply_text = result.reply_text
    session.history.append(ChatMessage(role="assistant", content=reply_text))
    _store.save(session)
    return ChatResponse(
        session_id=session.session_id,
        reply_text=reply_text,
        quick_replies=result.quick_replies,
        needs_platform_selection=result.needs_platform_selection and not session.platforms_resolved,
        available_platforms=recommender.available_platform_names() if result.needs_platform_selection else [],
        selected_platforms=session.slots.platforms,
        language=session.language,
    )


@app.post("/api/platforms", response_model=ChatResponse)
def submit_platforms(payload: PlatformsRequest) -> ChatResponse:
    with _store.session_lock(payload.session_id):
        return _submit_platforms_impl(payload)


def _submit_platforms_impl(payload: PlatformsRequest) -> ChatResponse:
    session = _store.get(payload.session_id)
    matched = recommender.match_catalog_platforms(payload.platforms) if payload.platforms else []
    session.slots.platforms = matched
    session.platforms_resolved = True

    reply_text, recommendations = _run_recommendations(session)
    return ChatResponse(
        session_id=session.session_id,
        reply_text=reply_text,
        quick_replies=_post_recommend_quick_replies(session.language),
        selected_platforms=session.slots.platforms,
        recommendations=recommendations,
        language=session.language,
    )


def _run_recommendations(session) -> tuple[str, list]:
    try:
        intro, recommendations, tried_titles = recommender.build_recommendations(
            session.slots,
            language=session.language,
            exclude_ids=set(session.recommended_ids),
            exclude_titles=session.recommended_titles,
        )
    except Exception:
        logger.exception("recommendation build failed")
        intro, recommendations, tried_titles = (
            "Sorry, I couldn't reach the movie database just now — mind trying again in a moment?",
            [],
            session.recommended_titles,
        )
    session.recommended_ids.extend(r.tmdb_id for r in recommendations)
    session.recommended_titles = tried_titles
    session.recommended = True

    # The frontend renders the recommendation cards from the API response, not from
    # this history text — but the model needs the real title/blurb of each pick in
    # its own context, or a later "what's the second one about?" gets hallucinated
    # against an unrelated same-titled movie from its training data instead of the
    # one actually shown.
    history_note = intro
    if recommendations:
        lines = [f"{r.title} ({r.year}) on {r.platform}: {r.blurb}" for r in recommendations]
        history_note = intro + "\n" + "\n".join(lines)
    session.history.append(ChatMessage(role="assistant", content=history_note))
    _store.save(session)
    return intro, recommendations
