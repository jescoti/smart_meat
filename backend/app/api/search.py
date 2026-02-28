"""Search API endpoint — full-text search across messages.

Uses the factory-router pattern for testability.  The search query is
handled via ``websearch_to_tsquery`` in the service layer — all user input
is parameterised, never interpolated into SQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search import MessageSearchHit, search_messages


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency — overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


def _get_user_id(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> str | None:
    """Extract user_id from request state (auth middleware) or X-User-Id header (testing)."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return str(user_id)
    return x_user_id


def _hit_to_dict(hit: MessageSearchHit) -> dict:
    """Serialize a MessageSearchHit to a JSON-safe dict."""
    return {
        "message_id": str(hit.message_id),
        "subject": hit.subject,
        "sender_name": hit.sender_name,
        "sender_email": hit.sender_email,
        "gmail_date": hit.gmail_date.isoformat() if hit.gmail_date else None,
        "snippet": hit.snippet,
        "group_id": str(hit.group_id),
        "thread_id": str(hit.thread_id) if hit.thread_id else None,
        "rank": hit.rank,
    }


def create_search_router() -> APIRouter:
    """Create an APIRouter with the search endpoint.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(tags=["search"])

    _session_dep = Depends(_get_session_dependency)

    @router.get("/api/search")
    async def search(
        q: str | None = None,
        group_id: uuid.UUID | None = None,
        sender: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=20, ge=1, le=100),
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Search messages across the user's groups.

        Query params:
            q: Search query (required, non-empty).
            group_id: Optional group UUID filter.
            sender: Optional sender email filter.
            date_from: Optional ISO datetime lower bound.
            date_to: Optional ISO datetime upper bound.
            page: Page number (default 1).
            per_page: Results per page (default 20, max 100).
        """
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        if q is None or q.strip() == "":
            return JSONResponse(
                status_code=400,
                content={"error": "bad_request", "message": "Search query is required"},
            )

        result = await search_messages(
            session=session,
            user_id=uuid.UUID(user_id),
            query=q.strip(),
            group_id=group_id,
            sender_email=sender,
            date_from=date_from,
            date_to=date_to,
            page=page,
            per_page=per_page,
        )

        return JSONResponse(
            status_code=200,
            content={
                "results": [_hit_to_dict(hit) for hit in result.results],
                "total": result.total,
                "page": result.page,
                "per_page": result.per_page,
            },
        )

    return router
