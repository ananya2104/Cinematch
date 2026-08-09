from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str

    tmdb_read_access_token: str

    watchmode_api_key: str

    omdb_api_key: str | None = None

    streaming_region: str = "IN"
    session_ttl_minutes: int = 120

    # Optional — e.g. "redis://:password@my-cache.redis.cache.windows.net:6380/0?ssl=true"
    # for Azure Cache for Redis, or "redis://localhost:6379/0" for local dev. Session
    # storage falls back to in-memory (per-process) automatically when this is unset.
    redis_url: str | None = None

    # Comma-separated list of origins allowed to call the API cross-origin — needed
    # once the frontend is hosted separately from the backend (e.g. GitHub Pages
    # calling an Azure-hosted API). Same-origin requests (frontend+backend on one
    # host) don't need this at all.
    cors_allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000,https://himanshu-bist-hb.github.io"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
