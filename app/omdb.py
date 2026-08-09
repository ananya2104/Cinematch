from __future__ import annotations

import threading

from cachetools import TTLCache, cached

from app.config import get_settings
from app.http_client import HttpError, get_json

BASE_URL = "https://www.omdbapi.com/"

_cache_lock = threading.Lock()
_rating_cache: TTLCache = TTLCache(maxsize=1024, ttl=86400)


@cached(_rating_cache, lock=_cache_lock)
def get_rating_by_imdb_id(imdb_id: str) -> float | None:
    settings = get_settings()
    if not settings.omdb_api_key:
        return None
    try:
        data = get_json(BASE_URL, params={"apikey": settings.omdb_api_key, "i": imdb_id}, timeout=10.0)
    except HttpError:
        return None
    rating = data.get("imdbRating")
    if not rating or rating == "N/A":
        return None
    try:
        return float(rating)
    except ValueError:
        return None
