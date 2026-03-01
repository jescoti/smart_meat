"""JWT authentication middleware for FastAPI.

Reads a JWT from the ``access_token`` httpOnly cookie, validates its
signature and expiry, and injects the authenticated ``user_id`` into
``request.state`` for downstream handlers.

Certain public paths (health, auth endpoints, non-API paths) are exempt
from authentication checks.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.jwt import verify_token

# Paths that do not require JWT authentication.
_SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/api/health",
        "/api/auth/login",
        "/api/auth/callback",
        "/api/auth/refresh",
        "/api/trigger-error",
    }
)


def _should_skip(path: str) -> bool:
    """Return True if the path should bypass authentication."""
    if path in _SKIP_PATHS:
        return True
    # Non-API paths are public
    if not path.startswith("/api/"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces JWT cookie authentication.

    Constructor Args:
        app: The ASGI application.
        secret_key: The HMAC secret used to verify JWT signatures.
    """

    def __init__(self, app: object, secret_key: str) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._secret_key = secret_key

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _should_skip(request.url.path):
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Missing access token",
                },
            )

        try:
            payload = verify_token(token, self._secret_key)
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Invalid or expired access token",
                },
            )

        request.state.user_id = payload["sub"]
        return await call_next(request)
