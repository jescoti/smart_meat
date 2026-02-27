"""FastAPI application entry point.

Defines the app instance, middleware, lifespan, and global error handling.
Never expose stack traces to callers — all unhandled exceptions return a
generic error envelope with a request_id for log correlation.
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch all unhandled exceptions and return a safe generic error response.

    This middleware runs outside Starlette's internal exception handler so it
    intercepts RuntimeError and other unhandled exceptions before they
    propagate to the ASGI server.  Stack traces are never included in the
    response body.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = str(uuid.uuid4())
            # TODO: emit structured log with request_id, exc type and message
            return JSONResponse(
                status_code=500,
                content={
                    "error": type(exc).__name__,
                    "message": "An unexpected error occurred. Please try again later.",
                    "request_id": request_id,
                },
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown.

    Database engine setup and teardown will be added here once the models
    layer is implemented (WU-2).
    """
    # Startup: placeholder for async DB engine initialisation
    yield
    # Shutdown: placeholder for async DB engine disposal


app = FastAPI(
    title="Smart Meat API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware — order matters: ErrorHandlerMiddleware must be added LAST so
# it is the outermost wrapper around all other middleware.
# ---------------------------------------------------------------------------

# Import settings lazily to allow tests to patch env vars before import.
from app.config import Settings  # noqa: E402  (placed after app creation)

_settings = Settings()  # type: ignore[call-arg]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last = executed first in the middleware stack
app.add_middleware(ErrorHandlerMiddleware)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Test-only route — exercises the global error handler
# ---------------------------------------------------------------------------


@app.get("/api/trigger-error")
async def trigger_error() -> None:
    """Intentionally raises an exception to exercise the global error handler."""
    raise RuntimeError("Intentional test error")
