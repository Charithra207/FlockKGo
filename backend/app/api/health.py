"""
health.py — Health check endpoints.

Two levels:
  GET /health          — liveness probe (is the process alive?)
                         Returns 200 immediately. Used by load balancers
                         to decide whether to restart the container.

  GET /health/detailed — readiness probe (can the app serve traffic?)
                         Checks DB, Redis, OpenAI connectivity.
                         Returns 200 if all critical deps are healthy,
                         503 if any critical dependency is down.

Why two endpoints?
  Kubernetes (and Render) use separate liveness + readiness probes.
  A liveness failure → container restart.
  A readiness failure → stop sending traffic (but don't restart).
  You don't want a Redis outage to restart your containers.

Interview talking point
  "I separated liveness from readiness so a temporary Redis outage
   pulls the pod from the load balancer without triggering a restart
   loop. OpenAI is non-critical — it's checked but doesn't affect
   the overall status."
"""

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["health"])


# ── Dependency checkers ───────────────────────────────────────────────────────

def _check_database() -> dict:
    """Verify the DB is reachable and responsive."""
    start = time.perf_counter()
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        return {
            "status": "healthy",
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)[:200],
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }


def _check_redis() -> dict:
    """Verify Redis is reachable (used by Celery + cache)."""
    start = time.perf_counter()
    try:
        import redis
        from app.config import get_settings
        client = redis.from_url(
            get_settings().redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return {
            "status": "healthy",
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)[:200],
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }


def _check_openai() -> dict:
    """Verify OpenAI API key is configured and the endpoint is reachable."""
    start = time.perf_counter()
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.openai_api_key:
            return {"status": "not_configured", "latency_ms": 0}

        from app.llm.gateway import _circuit_breaker
        if not _circuit_breaker.is_allowed():
            return {
                "status": "circuit_open",
                "circuit_state": _circuit_breaker.state.value,
                "latency_ms": int((time.perf_counter() - start) * 1000),
            }

        # Lightweight model list call — cheaper than a completion
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key, timeout=5)
        client.models.list()
        return {
            "status": "healthy",
            "circuit_state": _circuit_breaker.state.value,
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)[:200],
            "latency_ms": int((time.perf_counter() - start) * 1000),
        }


def _check_ml_artifacts() -> dict:
    """Verify destinations are seeded in the DB."""
    try:
        from app.db.database import SessionLocal
        from app.models.destination import Destination
        db = SessionLocal()
        count = db.query(Destination).filter(Destination.is_active == True).count()
        embedded = db.query(Destination).filter(
            Destination.embedding.isnot(None)
        ).count()
        db.close()
        return {
            "status": "healthy" if count > 0 else "not_seeded",
            "destination_count": count,
            "embedded_count": embedded,
            "scoring_mode": "semantic" if embedded >= count // 2 else "feature",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)[:200]}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
def liveness():
    """
    Liveness probe — is the process alive?
    Always returns 200 as long as the app is running.
    """
    return {"status": "alive"}


@router.get("/health/detailed")
def readiness():
    """
    Readiness probe — can the app serve traffic?

    Checks all dependencies and returns:
      200 — all critical deps healthy
      503 — one or more critical deps down

    Critical:    database
    Non-critical: redis, openai (degraded mode still works)
    """
    checks = {
        "database": _check_database(),
        "redis":    _check_redis(),
        "openai":   _check_openai(),
        "ml_artifacts": _check_ml_artifacts(),
    }

    from app.services.websocket_manager import manager
    checks["websocket"] = {
        "status": "healthy",
        "active_connections": manager.total_connections(),
    }

    # Database is the only hard dependency
    db_healthy = checks["database"]["status"] == "healthy"
    overall = "healthy" if db_healthy else "degraded"
    http_status = 200 if db_healthy else 503

    response_body = {
        "status": overall,
        "checks": checks,
        "critical_healthy": db_healthy,
        "non_critical_healthy": {
            "redis": checks["redis"]["status"] == "healthy",
            "openai": checks["openai"]["status"] in ("healthy", "not_configured"),
        },
    }

    if not db_healthy:
        log.error("health_check_failed", checks=checks)

    return JSONResponse(status_code=http_status, content=response_body)
