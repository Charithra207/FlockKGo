from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


def _normalize_db_url(url: str) -> str:
    """
    Render provides DATABASE_URL as postgres:// but SQLAlchemy
    requires postgresql+psycopg2://. Fix it silently.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


settings = get_settings()
database_url = _normalize_db_url(settings.database_url)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(
    database_url,
    pool_pre_ping=True,      # reconnect on stale connections
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
