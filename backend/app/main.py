from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest
from sqlalchemy.exc import OperationalError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import admin, analytics, budget, health as health_router, participants, recommendations, surveys, trips, voting, ws, sync_admin
from app.core.logging import configure_logging, get_logger
from app.core.middleware import AccessLogMiddleware, RequestIDMiddleware
from app.llm.gateway import LLMError
from app.ml.pipeline import MLPipelineError
from app.monitoring.metrics import llm_circuit_breaker_state, ws_active_connections

# Configure structured logging before anything else
configure_logging()
log = get_logger(__name__)

app = FastAPI(title="PackVote+ API", version="1.0.0")
app.state.limiter = trips.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def _create_tables():
    """Create all SQLite tables on first run (dev convenience)."""
    import app.models  # noqa: F401 — ensure all models are registered
    from app.db.database import Base, engine
    Base.metadata.create_all(bind=engine)


# ── Middleware (order matters — first added = outermost) ──────────────────────
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    # In production, FRONTEND_BASE_URL is set to the Vercel URL.
    # Credentials (cookies/auth headers) require an explicit origin — not "*".
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # all Vercel preview deploys
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(trips.router, prefix="/v1")
app.include_router(participants.router, prefix="/v1")
app.include_router(surveys.router, prefix="/v1")
app.include_router(recommendations.router, prefix="/v1")
app.include_router(voting.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")
app.include_router(budget.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")
app.include_router(sync_admin.router, prefix="/v1")
app.include_router(health_router.router)  # /health and /health/detailed (no prefix)
app.include_router(ws.router)


# ── Health + utility endpoints ────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "PackVote+ API", "docs": "/docs"}


@app.get("/ws/connections")
def ws_connections():
    from app.services.websocket_manager import manager
    return {"total_active_connections": manager.total_connections()}


@app.get("/metrics")
def metrics():
    # Update gauges with current values before scrape
    from app.services.websocket_manager import manager
    from app.llm.gateway import _circuit_breaker, CircuitState
    ws_active_connections.set(manager.total_connections())
    state_map = {CircuitState.CLOSED: 0, CircuitState.HALF_OPEN: 1, CircuitState.OPEN: 2}
    llm_circuit_breaker_state.set(state_map.get(_circuit_breaker.state, 0))
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": getattr(exc, "detail", "Resource not found")},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    log.warning("validation_error", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": exc.errors()},
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    log.error("llm_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "LLM error", "detail": str(exc)},
    )


@app.exception_handler(MLPipelineError)
async def ml_error_handler(request: Request, exc: MLPipelineError):
    log.error("ml_pipeline_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "ML pipeline error", "detail": str(exc)},
    )


@app.exception_handler(OperationalError)
async def db_unavailable_handler(request: Request, exc: OperationalError):
    log.error("db_unavailable", path=request.url.path)
    return JSONResponse(
        status_code=503,
        content={
            "error": "Database unavailable",
            "detail": "Configured database is not reachable. Start DB and retry.",
        },
    )


@app.exception_handler(Exception)
async def internal_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


