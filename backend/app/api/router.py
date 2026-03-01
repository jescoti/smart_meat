"""API router aggregation.

Provides a single ``api_router`` that aggregates all sub-routers.
Sub-routers already include ``/api/`` in their own prefixes, so this
router has no prefix to avoid double-prefixing (``/api/api/``).

This router is designed to be included in the FastAPI app instance
created in ``app.main``.
"""

from fastapi import APIRouter

from app.api.auth import create_auth_router
from app.api.consent import create_consent_router
from app.api.dashboard import create_dashboard_router
from app.api.groups import create_groups_router
from app.api.knowledge import create_knowledge_router
from app.api.messages import create_messages_router
from app.api.reply import create_reply_router
from app.api.search import create_search_router
from app.config import settings

api_router = APIRouter()

# Wire up sub-routers
api_router.include_router(
    create_auth_router(
        secret_key=settings.SECRET_KEY,
        encryption_key=settings.ENCRYPTION_KEY,
        google_client_id=settings.GOOGLE_CLIENT_ID,
        google_client_secret=settings.GOOGLE_CLIENT_SECRET,
        google_redirect_uri=settings.GOOGLE_REDIRECT_URI,
        frontend_url=settings.FRONTEND_URL,
        dev_login_enabled=settings.DEV_LOGIN_ENABLED,
    )
)
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
