from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlockGo API"
    environment: str = "development"
    database_url: str = "sqlite:///./flockgo_demo.db"
    redis_url: str = "redis://localhost:6379/0"
    # Dispatch ML jobs to Celery only if a worker is deployed. When False the
    # pipeline runs as a FastAPI background task inside the API process.
    use_celery: bool = False
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    frontend_base_url: str = "http://localhost:3000"
    # Master secret used to sign/verify API keys (set in production env)
    # If not set, auth is disabled in development mode
    api_secret_key: str | None = None

    # Signs user login tokens. Required in production (openssl rand -hex 32).
    auth_token_secret: str | None = None
    auth_token_ttl_days: int = 30

    # Give-a-spot-get-a-spot economy
    signup_bonus_credits: int = 1          # one free unlock to show the value
    credits_per_hidden_spot: int = 3       # reward when a hidden spot is approved
    credits_per_public_spot: int = 1       # reward when a cafe/public spot is approved
    # Comma-separated emails that become admin when they sign up / log in
    # (so you don't need a server shell to run make_admin.py).
    admin_emails: str = ""
    max_pending_submissions: int = 5       # anti-spam: per user
    report_threshold: int = 3              # this many people report a spot -> hidden until reviewed

    # Email (password reset, verification). Resend is simplest; SMTP also works.
    # With neither set, emails are only logged and features degrade gracefully.
    resend_api_key: str | None = None
    mail_from: str = "FlockGo <onboarding@resend.dev>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    # Only enforce once email actually works.
    require_email_verification: bool = False

    # Sign in with Google (Google Cloud console -> OAuth client ID, type "Web")
    google_client_id: str | None = None
    # Cloudflare Turnstile captcha on sign-up + sharing (optional)
    turnstile_secret: str | None = None
    turnstile_site_key: str | None = None   # public half, handed to the website
    # Error tracking (optional)
    sentry_dsn: str | None = None

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
