"""CSRF double-submit cookie middleware for FastAPI.

On mutating HTTP methods (POST, PUT, DELETE, PATCH), the middleware compares
the ``csrf_token`` cookie value against the ``X-CSRF-Token`` request header.
If they do not match (or either is missing/empty), the request is rejected
with 403.

Safe methods (GET, HEAD, OPTIONS) and exempt paths (health, auth endpoints,
non-API paths) are passed through without validation.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# HTTP methods that mutate state and require CSRF validation.
_MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# Paths that are exempt from CSRF validation.
_SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/api/health",
        "/api/auth/login",
        "/api/auth/callback",
        "/api/auth/refresh",
    }
)


def _should_skip(path: str) -> bool:
    """Return True if the path should bypass CSRF validation."""
    if path in _SKIP_PATHS:
        return True
    if not path.startswith("/api/"):
        return True
    return False


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Returns:
        A URL-safe random string of 32 bytes (43 characters).
    """
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing CSRF double-submit cookie pattern.

    On mutating HTTP methods for API paths, the ``csrf_token`` cookie must
    match the ``X-CSRF-Token`` header.  Both must be present and non-empty.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _should_skip(request.url.path):
            return await call_next(request)

        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token", "")
        header_token = request.headers.get("x-csrf-token", "")

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf_validation_failed",
                    "message": "CSRF token missing or mismatched",
                },
            )

        return await call_next(request)
