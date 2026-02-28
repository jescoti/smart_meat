"""API router aggregation.

Provides a single ``api_router`` that aggregates all sub-routers under the
``/api`` prefix.  This router is designed to be included in the FastAPI app
instance created in ``app.main``.

Re-exports factory functions for routers that manage their own prefixes
(auth, consent) and are mounted directly on the FastAPI app instance.
"""

from fastapi import APIRouter

from app.api.consent import create_consent_router

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}


__all__ = ["api_router", "create_consent_router"]
