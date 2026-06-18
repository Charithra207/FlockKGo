"""
middleware.py — Request ID middleware + access logging.

RequestIDMiddleware
  - Generates a unique request_id (UUID4) for every HTTP request.
  - Reads X-Request-ID header if the client provides one (useful for
    tracing across frontend → backend → worker).
  - Injects the request_id into structlog's context variables so every
    log line emitted during that request automatically includes it.
  - Returns X-Request-ID in the response headers so the client can
    correlate their own logs.

AccessLogMiddleware
  - Logs every request/response as a structured JSON line with:
    method, path, status_code, duration_ms, request_id.
  - Skips /health and /metrics to avoid log noise.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger("app.middleware")

SKIP_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assign a unique request_id to every request.
    Injects it into structlog context so all logs for this request
    automatically include the request_id field.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use client-provided ID if present (allows frontend→backend tracing)
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Store on request state so other middleware/handlers can access it
        request.state.request_id = request_id

        response = await call_next(request)

        # Return the ID in response headers
        response.headers["X-Request-ID"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Log every request as a structured JSON line.
    Skips noisy health/metrics endpoints.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            log.error(
                "unhandled_exception",
                exc_info=exc,
                path=request.url.path,
            )
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            level = "warning" if status_code >= 400 else "info"

            getattr(log, level)(
                "http_request",
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=request.client.host if request.client else "unknown",
            )
