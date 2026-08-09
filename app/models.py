from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Slots(BaseModel):
    basis: str | None = None  # how the user wants picks chosen: genre_mood / person_or_franchise / release_era / persona
    mood: str | None = None
    genres: list[str] = Field(default_factory=list)
    duration_max_minutes: int | None = None
    industry: str | None = None  # e.g. "bollywood", "tollywood", "hollywood", "kollywood"
    company: str | None = None  # e.g. "alone", "date", "family", "friends"
    recency: str | None = None  # "new" or "old"
    era: str | None = None  # a specific decade/era ask, e.g. "90s", "2010s", "classic Hollywood"
    min_rating: float | None = None  # 0-10, TMDB scale
    topic: str | None = None  # a franchise/keyword ask, e.g. "marvel", "james bond", "time travel"
    actor: str | None = None
    director: str | None = None
    platforms: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    ui_language: str | None = None  # explicit override from the language picker


class PlatformsRequest(BaseModel):
    session_id: str
    platforms: list[str]


class Recommendation(BaseModel):
    tmdb_id: int
    title: str
    year: str | None = None
    poster_url: str | None = None
    platform: str | None = None
    blurb: str
    watch_url: str
    imdb_rating: float | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply_text: str
    quick_replies: list[str] = Field(default_factory=list)
    needs_platform_selection: bool = False
    available_platforms: list[str] = Field(default_factory=list)
    selected_platforms: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    language: str = "en"


class DialogueTurnResult(BaseModel):
    reply_text: str
    detected_language: str
    basis: str | None = None
    mood: str | None = None
    genres: list[str] = Field(default_factory=list)
    duration_max_minutes: int | None = None
    industry: str | None = None
    company: str | None = None
    recency: str | None = None
    era: str | None = None
    min_rating: float | None = None
    topic: str | None = None
    actor: str | None = None
    director: str | None = None
    platforms_mentioned: list[str] = Field(default_factory=list)
    ready_to_recommend: bool
    needs_platform_selection: bool
    wants_recommendations: bool
    quick_replies: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionState(BaseModel):
    session_id: str
    history: list[ChatMessage] = Field(default_factory=list)
    slots: Slots = Field(default_factory=Slots)
    language: str = "en"
    turn_count: int = 0
    recommended: bool = False
    platforms_resolved: bool = False
    recommended_ids: list[int] = Field(default_factory=list)
    recommended_titles: list[str] = Field(default_factory=list)
    last_seen: float = 0.0
