from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app import llm, omdb, tmdb, watchmode
from app.config import get_settings
from app.models import Recommendation, Slots

logger = logging.getLogger("cinematch")

MAX_ROUNDS = 2
FIRST_ROUND_COUNT = 10
RETRY_ROUND_COUNT = 8
# Some networks (see app/http_client.py) reset connections outright once too many
# land on the same host at once — stacking this with a second level of concurrency
# per-candidate pushed that past the breaking point, so this is intentionally modest
# rather than as high as the machine could otherwise sustain.
VERIFY_WORKERS = 3

# Curated to what's actually on TMDB's India catalog today (Disney+ Hotstar and
# JioCinema merged into JioHotstar in 2025; HBO Max isn't offered in India).
PLATFORM_CATALOG = [
    {"display": "Netflix", "tmdb": "Netflix", "watchmode": "Netflix"},
    {"display": "Prime Video", "tmdb": "Amazon Prime Video", "watchmode": "Amazon Prime Video"},
    {"display": "JioHotstar", "tmdb": "JioHotstar", "watchmode": "JioHotstar"},
    {"display": "Apple TV+", "tmdb": "Apple TV", "watchmode": "Apple TV+"},
    {"display": "SonyLIV", "tmdb": "Sony Liv", "watchmode": "SonyLIV"},
    {"display": "Zee5", "tmdb": "Zee5", "watchmode": "Zee5"},
]


def available_platform_names() -> list[str]:
    return [p["display"] for p in PLATFORM_CATALOG]


def _catalog_entry(display_name: str) -> dict | None:
    norm = display_name.strip().lower()
    for entry in PLATFORM_CATALOG:
        if entry["display"].lower() == norm:
            return entry
    return None


def match_catalog_platforms(names: list[str]) -> list[str]:
    """Fuzzy-match free-text platform mentions (e.g. from LLM extraction) to canonical display names."""
    matched: list[str] = []
    for name in names:
        norm = "".join(ch for ch in name.lower() if ch.isalnum())
        for entry in PLATFORM_CATALOG:
            entry_norm = "".join(ch for ch in entry["display"].lower() if ch.isalnum())
            if norm in entry_norm or entry_norm in norm:
                if entry["display"] not in matched:
                    matched.append(entry["display"])
                break
    return matched


def _resolve_watch_info(tmdb_id: int, region: str, preferred_platforms: list[dict]) -> tuple[str | None, str | None]:
    """Returns (platform_display_name, watch_url) or (None, None) if not actually available
    on one of the user's selected platforms (or anywhere, if none were selected)."""
    wp = tmdb.get_movie_watch_providers(tmdb_id, region)
    flatrate = wp.get("flatrate", []) + wp.get("ads", [])
    available_names = {p.get("provider_name", "").lower() for p in flatrate}

    candidates = preferred_platforms or PLATFORM_CATALOG
    for entry in candidates:
        if entry["tmdb"].lower() in available_names:
            deep_link = watchmode.find_deep_link(tmdb_id, entry["watchmode"], region)
            return entry["display"], (deep_link or wp.get("link"))

    return None, None


def _imdb_rating(tmdb_id: int) -> float | None:
    imdb_id = tmdb.get_imdb_id(tmdb_id)
    return omdb.get_rating_by_imdb_id(imdb_id) if imdb_id else None


def _verify_suggestion(
    s: dict,
    exclude_ids: set[int],
    region: str,
    preferred: list[dict],
    min_rating: float | None,
) -> tuple[str | None, dict | None]:
    """Looks up one LLM-suggested title on TMDB and checks real availability/rating.
    Returns (tried_title, picked_dict) — picked_dict is None if it didn't pan out.
    Runs inside a worker thread; only reads exclude_ids (the caller dedupes/mutates
    it afterward on the main thread, since these calls run concurrently).

    Never raises: a network blip on one candidate (more likely now that several run
    at once — see VERIFY_WORKERS above) should drop just that candidate, not blow up
    the whole batch when another thread calls .result() on this one's future."""
    title = (s.get("title") or "").strip()
    year = s.get("year")
    if not title:
        return None, None
    tried_title = f"{title} ({year})" if year else title

    try:
        match = tmdb.search_movie(title, year)
        if not match or match["id"] in exclude_ids:
            return tried_title, None
        if min_rating and (match.get("vote_average") or 0) < min_rating:
            return tried_title, None

        platform, watch_url = _resolve_watch_info(match["id"], region, preferred)
        imdb_rating = _imdb_rating(match["id"]) if watch_url else None
    except Exception:
        logger.warning("Skipping suggestion %r after a lookup failure", title, exc_info=True)
        return tried_title, None

    if not watch_url:
        return tried_title, None

    return tried_title, {
        "tmdb_id": match["id"],
        "title": match.get("title") or title,
        "year": (match.get("release_date") or "")[:4] or (str(year) if year else None),
        "poster_url": tmdb.poster_url(match.get("poster_path")),
        "imdb_rating": imdb_rating,
        "platform": platform,
        "watch_url": watch_url,
        "blurb": s.get("blurb", ""),
    }


def build_recommendations(
    slots: Slots,
    *,
    region: str | None = None,
    limit: int = 4,
    language: str = "en",
    exclude_ids: set[int] | None = None,
    exclude_titles: list[str] | None = None,
) -> tuple[str, list[Recommendation], list[str]]:
    """The LLM picks specific real movies from its own knowledge, matching the whole
    conversation; each suggestion is then looked up on TMDB and only kept if it's
    genuinely streaming on the user's selected platform(s). If too many suggestions
    turn out unavailable, a second round asks the model to prioritize availability.

    Returns (intro, recommendations, titles_tried) — the caller should remember
    titles_tried for next time so repeat/failed suggestions aren't re-offered.
    """
    region = region or get_settings().streaming_region
    exclude_ids = set(exclude_ids or set())
    tried_titles = list(exclude_titles or [])
    preferred = [e for name in slots.platforms if (e := _catalog_entry(name))]

    picked: list[dict] = []
    intro = "Here's what I'd recommend —"

    for round_num in range(MAX_ROUNDS):
        if len(picked) >= limit:
            break
        count = FIRST_ROUND_COUNT if round_num == 0 else RETRY_ROUND_COUNT
        round_intro, suggestions = llm.suggest_movies(
            slots,
            exclude_titles=tried_titles,
            language=language,
            count=count,
            broaden=(round_num > 0),
        )
        if not suggestions:
            continue
        intro = round_intro

        # Verify every suggestion in this round concurrently (each is an independent
        # chain of TMDB/Watchmode/OMDb lookups) instead of one at a time — this is
        # the dominant cost of a recommendation request, so this cuts wall-clock time
        # from roughly the sum of all candidates' latency down to the slowest one.
        with ThreadPoolExecutor(max_workers=VERIFY_WORKERS) as pool:
            results = [
                f.result()
                for f in [
                    pool.submit(_verify_suggestion, s, exclude_ids, region, preferred, slots.min_rating)
                    for s in suggestions
                ]
            ]

        for tried_title, result in results:
            if tried_title:
                tried_titles.append(tried_title)
            if result is None or result["tmdb_id"] in exclude_ids:
                continue
            if len(picked) >= limit:
                break
            picked.append(result)
            exclude_ids.add(result["tmdb_id"])

    if not picked:
        return (
            "I couldn't find any confirmed matches on your platforms right now — want to try a different genre or add another platform?",
            [],
            tried_titles,
        )

    recommendations = [
        Recommendation(
            tmdb_id=p["tmdb_id"],
            title=p["title"],
            year=p["year"],
            poster_url=p["poster_url"],
            platform=p["platform"],
            blurb=p["blurb"],
            watch_url=p["watch_url"],
            imdb_rating=p["imdb_rating"],
        )
        for p in picked
    ]
    return intro, recommendations, tried_titles
