from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlockGo API"
    environment: str = "development"
    # Demo-friendly default: local SQLite file (no Docker/Postgres required).
    database_url: str = "sqlite:///./flockgo_demo.db"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
