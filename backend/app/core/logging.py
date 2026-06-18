"""
logging.py — Structured JSON logging configuration.

Every log line is a JSON object with consistent fields:
  {
    "timestamp": "2025-01-01T12:00:00Z",
    "level": "info",
    "event": "ml_pipeline_complete",
    "request_id": "abc123",          ← traces one request end-to-end
    "trip_id": "uuid",
    "duration_ms": 1240,
    "logger": "app.ml.pipeline"
  }

Why this matters for interviews
---------------------------------
  "I replaced print() statements with structured JSON logs using structlog.
   Every request gets a correlation ID that propagates through the ML
   pipeline, Celery task, and LLM gateway. In production you can grep
   a single request_id across all services to reconstruct the full trace."

Usage
-----
  from app.core.logging import get_logger
  log = get_logger(__name__)
  log.info("ml_pipeline_complete", trip_id=str(trip_id), duration_ms=1240)
  log.error("llm_call_failed", model="gpt-4o", error=str(exc))
"""

import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    """
    Configure structlog + stdlib logging.
    Call once at app startup (in main.py).

    In development: colored console output (human-readable).
    In production:  JSON output (machine-parseable by log aggregators).
    """
    settings = get_settings()
    is_production = settings.environment == "production"

    # ── Shared processors (run for every log record) ──────────────────────────
    shared_processors = [
        structlog.contextvars.merge_contextvars,          # inject request_id etc.
        structlog.stdlib.add_logger_name,                 # add "logger" field
        structlog.stdlib.add_log_level,                   # add "level" field
        structlog.processors.TimeStamper(fmt="iso"),      # add "timestamp" field
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        # JSON output — one log line per record, parseable by Datadog / CloudWatch
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colorful console output for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to route through structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger bound to the given module name."""
    return structlog.get_logger(name)
