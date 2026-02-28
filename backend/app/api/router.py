"""API router aggregation.

Provides a single ``api_router`` that aggregates all sub-routers under the
``/api`` prefix.  This router is designed to be included in the FastAPI app
instance created in ``app.main``.
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}
