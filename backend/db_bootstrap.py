"""
db_bootstrap.py — Bring the database schema up to date, safely, on any DB.

Why this exists
  The Alembic history doesn't create the base tables (the "initial_schema"
  migration only ALTERs ml_run_results). So `alembic upgrade head` fails on a
  brand-new database, e.g. a fresh Render/Neon Postgres.

What it does
  * No alembic_version yet (new DB, or one made by the app's create_all):
      create every table from the models, then `alembic stamp head`.
  * Otherwise: `alembic upgrade head` as normal.

Usage
    python db_bootstrap.py
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402

import app.models  # noqa: E402,F401  (register every model)
from app.db.database import Base, engine  # noqa: E402


def _has_version(conn) -> bool:
    if "alembic_version" not in inspect(conn).get_table_names():
        return False
    return conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() > 0


def main() -> None:
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    with engine.connect() as conn:
        versioned = _has_version(conn)
    if versioned:
        print("Existing schema: running migrations")
        command.upgrade(cfg, "head")
    else:
        print("Fresh / unversioned schema: creating tables and stamping head")
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
    print("Schema ready.")


if __name__ == "__main__":
    main()
