from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

from app.models import SessionState


class SessionStore(ABC):
    @abstractmethod
    def get(self, session_id: str) -> SessionState: ...

    @abstractmethod
    def save(self, state: SessionState) -> None: ...

    @abstractmethod
    def session_lock(self, session_id: str) -> threading.Lock:
        """A lock scoped to one session, so a client firing two requests for the
        same session back-to-back (e.g. a double-click) can't race and clobber
        each other's read-modify-write of the session state."""
        ...


MAX_HISTORY_MESSAGES = 60


class InMemorySessionStore(SessionStore):
    """Process-local session store with TTL eviction.

    Swappable for a Redis-backed implementation later (same interface)
    if the app needs to scale beyond a single instance.
    """

    def __init__(self, ttl_minutes: int = 120):
        self._ttl_seconds = ttl_minutes * 60
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionState] = {}
        self._session_locks: dict[str, threading.Lock] = {}

    def session_lock(self, session_id: str) -> threading.Lock:
        with self._lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            self._evict_expired()
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id, last_seen=time.time())
                self._sessions[session_id] = state
            return state.model_copy(deep=True)

    def save(self, state: SessionState) -> None:
        state.last_seen = time.time()
        if len(state.history) > MAX_HISTORY_MESSAGES:
            # The LLM call only ever looks at the last 12 anyway (see llm.py) — this
            # just stops a very long-running session's transcript from growing
            # memory (and localStorage on the client) without bound.
            state.history = state.history[-MAX_HISTORY_MESSAGES:]
        with self._lock:
            self._sessions[state.session_id] = state

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_seen > self._ttl_seconds]
        for sid in expired:
            del self._sessions[sid]


class RedisSessionStore(SessionStore):
    """Redis-backed session store — same interface as InMemorySessionStore, but
    conversation state survives a restart/redeploy and is shared correctly across
    multiple app instances (e.g. Azure App Service scaled out, or several Uvicorn
    workers). Session locking uses a real distributed Redis lock instead of an
    in-process one, so it's still safe under concurrent requests across instances.

    Enabled by setting REDIS_URL (see app/config.py) — falls back to
    InMemorySessionStore automatically when unset, so local dev needs no Redis.
    """

    def __init__(self, redis_url: str, ttl_minutes: int = 120):
        import redis  # local import: only required when REDIS_URL is actually set

        self._ttl_seconds = ttl_minutes * 60
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"cinematch:session:{session_id}"

    def session_lock(self, session_id: str):
        return self._client.lock(f"cinematch:lock:{session_id}", timeout=30, blocking_timeout=10)

    def get(self, session_id: str) -> SessionState:
        raw = self._client.get(self._key(session_id))
        if raw is None:
            return SessionState(session_id=session_id, last_seen=time.time())
        return SessionState.model_validate_json(raw)

    def save(self, state: SessionState) -> None:
        state.last_seen = time.time()
        if len(state.history) > MAX_HISTORY_MESSAGES:
            state.history = state.history[-MAX_HISTORY_MESSAGES:]
        self._client.set(self._key(state.session_id), state.model_dump_json(), ex=self._ttl_seconds)
