from __future__ import annotations

import threading

from cachetools import TTLCache, cached

from app.config import get_settings
from app.http_client import HttpError, get_json

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

_cache_lock = threading.Lock()
_imdb_id_cache: TTLCache = TTLCache(maxsize=1024, ttl=86400)
_providers_cache: TTLCache = TTLCache(maxsize=1024, ttl=3600)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_settings().tmdb_read_access_token}",
        "accept": "application/json",
    }


def _get(path: str, params: dict | None = None) -> dict:
    return get_json(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=15.0)


def search_movie(title: str, year: int | None = None) -> dict | None:
    """Look up a specific movie the LLM suggested, by title (+ optional year to
    disambiguate). Returns the best-matching TMDB result, or None if nothing real
    matches (or the lookup failed) — the caller drops the suggestion in that case
    rather than showing it, or letting one bad candidate fail the whole batch."""
    params = {"query": title, "include_adult": "false", "language": "en-US"}
    if year:
        params["year"] = year
    try:
        data = _get("/search/movie", params=params)
    except HttpError:
        return None
    results = data.get("results", [])
    if not results and year:
        # The model's year guess might be slightly off — retry without it.
        try:
            data = _get("/search/movie", params={"query": title, "include_adult": "false", "language": "en-US"})
        except HttpError:
            return None
        results = data.get("results", [])
    return results[0] if results else None


@cached(_imdb_id_cache, lock=_cache_lock)
def get_imdb_id(movie_id: int) -> str | None:
    try:
        data = _get(f"/movie/{movie_id}/external_ids")
    except HttpError:
        return None
    return data.get("imdb_id") or None


@cached(_providers_cache, key=lambda movie_id, region="IN": (movie_id, region), lock=_cache_lock)
def get_movie_watch_providers(movie_id: int, region: str = "IN") -> dict:
    try:
        data = _get(f"/movie/{movie_id}/watch/providers")
    except HttpError:
        return {}
    return data.get("results", {}).get(region, {})


def poster_url(poster_path: str | None) -> str | None:
    return f"{IMAGE_BASE}{poster_path}" if poster_path else None
