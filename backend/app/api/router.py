"""API router aggregation.

Provides a single ``api_router`` that aggregates all sub-routers under the
``/api`` prefix.  This router is designed to be included in the FastAPI app
instance created in ``app.main``.
"""

from fastapi import APIRouter

from app.api.consent import create_consent_router
from app.api.dashboard import create_dashboard_router
from app.api.groups import create_groups_router
from app.api.knowledge import create_knowledge_router
from app.api.messages import create_messages_router
from app.api.reply import create_reply_router
from app.api.search import create_search_router
from app.config import settings

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}


# Wire up sub-routers
api_router.include_router(create_consent_router())
api_router.include_router(
    create_groups_router(
        encryption_key=settings.ENCRYPTION_KEY,
        google_client_id=settings.GOOGLE_CLIENT_ID,
        google_client_secret=settings.GOOGLE_CLIENT_SECRET,
    )
)
api_router.include_router(create_messages_router())
api_router.include_router(create_knowledge_router())
api_router.include_router(create_reply_router())
api_router.include_router(create_search_router())
api_router.include_router(create_dashboard_router())
