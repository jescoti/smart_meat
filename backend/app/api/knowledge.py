"""Knowledge API endpoints — nugget CRUD and LLM extraction.

Provides endpoints for listing, creating, accepting/rejecting nuggets
and triggering LLM-based extraction from threads.

The router is created via ``create_knowledge_router()`` following the
factory pattern used by other routers.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Nugget, NuggetStatus
from app.middleware.consent import require_llm_consent
from app.services.knowledge import (
    accept_suggestion,
    create_manual_nugget,
    get_nugget,
    list_nuggets,
    process_thread_for_nuggets,
    reject_suggestion,
)


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


class CreateNuggetRequest(BaseModel):
    """Request body for creating a manual nugget."""

    group_id: uuid.UUID
    source_message_id: uuid.UUID | None = None
    title: str
    content: str
    tags: list[str] = []


def _nugget_to_dict(nugget: Nugget) -> dict:
    """Serialize a Nugget ORM object to a JSON-safe dict."""
    return {
        "id": str(nugget.id),
        "group_id": str(nugget.group_id),
        "source_message_id": str(nugget.source_message_id) if nugget.source_message_id else None,
        "title": nugget.title,
        "content": nugget.content,
        "tags": nugget.tags or [],
        "source_type": str(nugget.source_type),
        "status": str(nugget.status),
        "created_by": str(nugget.created_by),
        "created_at": nugget.created_at.isoformat() if nugget.created_at else None,
        "updated_at": nugget.updated_at.isoformat() if nugget.updated_at else None,
    }


def create_knowledge_router() -> APIRouter:
    """Create an APIRouter with knowledge base endpoints.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

    _session_dep = Depends(_get_session_dependency)

    @router.get("/nuggets")
    async def list_nuggets_endpoint(
        request: Request,
        group_id: uuid.UUID = Query(...),
        status: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=20, ge=1, le=100),
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """List nuggets for a group with optional status filter."""
        user_id = request.state.user_id

        # Parse status filter
        status_enum: NuggetStatus | None = None
        if status is not None:
            status_enum = NuggetStatus(status)

        nuggets, total = await list_nuggets(
            session=session,
            user_id=uuid.UUID(user_id),
            group_id=group_id,
            status=status_enum,
            page=page,
            per_page=per_page,
        )

        return JSONResponse(
            status_code=200,
            content={
                "nuggets": [_nugget_to_dict(n) for n in nuggets],
                "total": total,
                "page": page,
                "per_page": per_page,
            },
        )

    @router.get("/nuggets/{nugget_id}")
    async def get_nugget_endpoint(
        request: Request,
        nugget_id: uuid.UUID,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Get a single nugget by ID."""
        user_id = request.state.user_id

        nugget = await get_nugget(
            session=session,
            user_id=uuid.UUID(user_id),
            nugget_id=nugget_id,
        )

        if nugget is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Nugget not found"},
            )

        return JSONResponse(
            status_code=200,
            content=_nugget_to_dict(nugget),
        )

    @router.post("/nuggets")
    async def create_nugget_endpoint(
        request: Request,
        body: CreateNuggetRequest,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Create a manual nugget."""
        user_id = request.state.user_id

        nugget = await create_manual_nugget(
            session=session,
            user_id=uuid.UUID(user_id),
            group_id=body.group_id,
            source_message_id=body.source_message_id,
            title=body.title,
            content=body.content,
            tags=body.tags,
        )
        await session.commit()

        return JSONResponse(
            status_code=201,
            content=_nugget_to_dict(nugget),
        )

    @router.post("/nuggets/{nugget_id}/accept")
    async def accept_nugget_endpoint(
        request: Request,
        nugget_id: uuid.UUID,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Accept a suggested nugget."""
        user_id = request.state.user_id

        nugget = await accept_suggestion(
            session=session,
            user_id=uuid.UUID(user_id),
            nugget_id=nugget_id,
        )

        if nugget is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Nugget not found"},
            )

        await session.commit()

        return JSONResponse(
            status_code=200,
            content=_nugget_to_dict(nugget),
        )

    @router.post("/nuggets/{nugget_id}/reject")
    async def reject_nugget_endpoint(
        request: Request,
        nugget_id: uuid.UUID,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Reject a suggested nugget."""
        user_id = request.state.user_id

        nugget = await reject_suggestion(
            session=session,
            user_id=uuid.UUID(user_id),
            nugget_id=nugget_id,
        )

        if nugget is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Nugget not found"},
            )

        await session.commit()

        return JSONResponse(
            status_code=200,
            content=_nugget_to_dict(nugget),
        )

    @router.post("/threads/{thread_id}/extract")
    async def extract_from_thread_endpoint(
        request: Request,
        thread_id: uuid.UUID,
        _consent: None = Depends(require_llm_consent),
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Trigger LLM extraction for a thread. Requires LLM consent."""
        user_id = request.state.user_id

        try:
            nuggets = await process_thread_for_nuggets(
                session=session,
                thread_id=thread_id,
                user_id=uuid.UUID(user_id),
                model=settings.CLAUDE_MODEL,
                api_key=settings.ANTHROPIC_API_KEY,
            )
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"detail": str(e)},
            )

        await session.commit()

        return JSONResponse(
            status_code=200,
            content={
                "nuggets": [_nugget_to_dict(n) for n in nuggets],
            },
        )

    return router
