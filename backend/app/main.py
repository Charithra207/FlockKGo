from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import analytics, participants, recommendations, surveys, trips, voting
from app.db.database import Base, engine
from app.llm.gateway import LLMError
from app.ml.pipeline import MLPipelineError

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FlockGo API", version="1.0.0")
app.state.limiter = trips.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router, prefix="/v1")
app.include_router(participants.router, prefix="/v1")
app.include_router(surveys.router, prefix="/v1")
app.include_router(recommendations.router, prefix="/v1")
app.include_router(voting.router, prefix="/v1")
app.include_router(analytics.router, prefix="/v1")


@app.get("/")
def root():
    return {"message": "FlockGo API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": "Not found", "detail": getattr(exc, "detail", "Resource not found")})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "Validation error", "detail": exc.errors()})


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})


@app.exception_handler(MLPipelineError)
async def ml_error_handler(request: Request, exc: MLPipelineError):
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})


@app.exception_handler(Exception)
async def internal_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": str(exc)})
