import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make sure the backend root (where `app/` lives) is on the path so that
# `from app.xxx import yyy` works when Alembic runs from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import ALL models so Alembic can detect them for autogenerate.
# Adding a new model? Import it here.
# ---------------------------------------------------------------------------
from app.db.database import Base  # noqa: E402  (must come after sys.path setup)
import app.models.trip             # noqa: F401
import app.models.participant      # noqa: F401
import app.models.survey_response  # noqa: F401
import app.models.recommendation   # noqa: F401
import app.models.vote             # noqa: F401
import app.models.ml_result        # noqa: F401
import app.models.destination      # noqa: F401
import app.models.task_run         # noqa: F401
import app.models.prompt_version   # noqa: F401
import app.models.api_key          # noqa: F401

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Read DATABASE_URL from environment, falling back to the app's own config.
# This means `alembic upgrade head` works both locally (SQLite) and in
# production (Postgres) without changing any files.
# ---------------------------------------------------------------------------
def get_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Render provides postgres:// — SQLAlchemy needs postgresql+psycopg2://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        return url
    # Fall back to app settings (reads .env file)
    from app.config import get_settings
    return get_settings().database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL without a live DB
    connection. Useful for reviewing what will be applied before running.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the DB and applies changes.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # detect column type changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
