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

from app.api.router import api_router
from app.db.engine import dispose_db, get_session, init_db
from app.middleware.auth import AuthMiddleware

# Session dependency placeholders from each router module — these will be
# overridden with the real get_session after the app is created.
from app.api.auth import _get_session_dependency as _auth_session_dep
from app.api.consent import _get_session_dependency as _consent_session_dep
from app.api.dashboard import _get_session_dependency as _dashboard_session_dep
from app.api.groups import _get_session_dependency as _groups_session_dep
from app.api.knowledge import _get_session_dependency as _knowledge_session_dep
from app.api.messages import _get_session_dependency as _messages_session_dep
from app.api.reply import _get_session_dependency as _reply_session_dep
from app.api.search import _get_session_dependency as _search_session_dep
from app.middleware.consent import _get_session_dependency as _consent_mw_session_dep


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

    Initializes the database engine on startup and disposes it on shutdown.
    """
    from app.config import Settings

    _settings = Settings()  # type: ignore[call-arg]
    init_db(_settings.DATABASE_URL)
    yield
    await dispose_db()


app = FastAPI(
    title="Smart Meat API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Include the aggregated API router
# ---------------------------------------------------------------------------
app.include_router(api_router)

# ---------------------------------------------------------------------------
# Override all session dependency placeholders with the real get_session
# ---------------------------------------------------------------------------
app.dependency_overrides[_auth_session_dep] = get_session
app.dependency_overrides[_consent_session_dep] = get_session
app.dependency_overrides[_dashboard_session_dep] = get_session
app.dependency_overrides[_groups_session_dep] = get_session
app.dependency_overrides[_knowledge_session_dep] = get_session
app.dependency_overrides[_messages_session_dep] = get_session
app.dependency_overrides[_reply_session_dep] = get_session
app.dependency_overrides[_search_session_dep] = get_session
app.dependency_overrides[_consent_mw_session_dep] = get_session

# ---------------------------------------------------------------------------
# Middleware — order matters in Starlette:
#   add_middleware adds to FRONT of the chain, so the LAST added is outermost.
#   We want: CORS (outermost) → AuthMiddleware → ErrorHandler (innermost)
#   So we add: ErrorHandler first, then Auth, then CORS last.
# ---------------------------------------------------------------------------

# Import settings lazily to allow tests to patch env vars before import.
from app.config import Settings  # noqa: E402  (placed after app creation)

_settings = Settings()  # type: ignore[call-arg]

# ErrorHandler — innermost, catches unhandled exceptions
app.add_middleware(ErrorHandlerMiddleware)

# AuthMiddleware — validates JWT cookies, sets request.state.user_id
app.add_middleware(AuthMiddleware, secret_key=_settings.SECRET_KEY)

# CORS — outermost, must handle preflight OPTIONS before auth checks
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Standalone routes (not part of the aggregated router)
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
