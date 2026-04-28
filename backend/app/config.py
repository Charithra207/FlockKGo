from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlockGo API"
    environment: str = "development"
    # Default to local Postgres host for non-docker runs.
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/flockgo"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
