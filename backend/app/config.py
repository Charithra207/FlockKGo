from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlockGo API"
    environment: str = "development"
    database_url: str = "sqlite:///./flockgo_demo.db"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    frontend_base_url: str = "http://localhost:3000"
    # Master secret used to sign/verify API keys (set in production env)
    # If not set, auth is disabled in development mode
    api_secret_key: str | None = None

    # India Sync settings
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    osm_batch_size: int = 500
    opentripmap_api_key: str | None = None
    sync_schedule_cron: str = "0 2 * * 0"
    quality_threshold_high: int = 70
    quality_threshold_medium: int = 50
    catalog_max_active: int = 20_000

    # Bus & Travel API (Module 3 — Bus & Room Logistics Integrator)
    trawex_api_url: str | None = None      # e.g. "https://api.trawex.com/v1"
    trawex_api_key: str | None = None      # Trawex partner API key

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
