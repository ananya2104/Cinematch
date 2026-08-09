from __future__ import annotations

import threading

from cachetools import TTLCache, cached

from app.config import get_settings
from app.http_client import HttpError, get_json

BASE_URL = "https://api.watchmode.com/v1"

_cache_lock = threading.Lock()
_watchmode_id_cache: TTLCache = TTLCache(maxsize=512, ttl=86400)
_sources_cache: TTLCache = TTLCache(maxsize=512, ttl=3600)


def _get(path: str, params: dict | None = None) -> dict | list:
    params = dict(params or {})
    params["apiKey"] = get_settings().watchmode_api_key
    return get_json(f"{BASE_URL}{path}", params=params, timeout=15.0)


def _watchmode_id_for_tmdb(tmdb_id: int) -> int | None:
    with _cache_lock:
        if tmdb_id in _watchmode_id_cache:
            return _watchmode_id_cache[tmdb_id]
    try:
        data = _get("/search/", params={"search_field": "tmdb_movie_id", "search_value": tmdb_id})
    except HttpError:
        with _cache_lock:
            _watchmode_id_cache[tmdb_id] = None
        return None
    results = data.get("title_results", []) if isinstance(data, dict) else []
    watchmode_id = results[0]["id"] if results else None
    with _cache_lock:
        _watchmode_id_cache[tmdb_id] = watchmode_id
    return watchmode_id


@cached(_sources_cache, key=lambda tmdb_id, region="IN": (tmdb_id, region), lock=_cache_lock)
def get_title_sources(tmdb_id: int, region: str = "IN") -> list[dict]:
    """[{name, web_url, type}] streaming sources for a movie in `region`."""
    watchmode_id = _watchmode_id_for_tmdb(tmdb_id)
    if not watchmode_id:
        return []
    try:
        data = _get(f"/title/{watchmode_id}/sources/")
    except HttpError:
        return []
    if not isinstance(data, list):
        return []
    return [
        {"name": s.get("name"), "web_url": s.get("web_url"), "type": s.get("type")}
        for s in data
        if s.get("region") == region and s.get("web_url")
    ]


def find_deep_link(tmdb_id: int, platform_name: str, region: str = "IN") -> str | None:
    sources = get_title_sources(tmdb_id, region)
    wanted = _normalize(platform_name)
    for s in sources:
        if wanted in _normalize(s.get("name", "")) or _normalize(s.get("name", "")) in wanted:
            return s.get("web_url")
    return None


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())
