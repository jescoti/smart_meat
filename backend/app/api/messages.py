"""Messages API endpoints — thread listing and thread detail.

Provides paginated thread listing for a group and full thread detail
with message hierarchy. Uses the same factory-router pattern as other
routers for testability.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Group, Message, Thread, ThreadMessage


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
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


def _thread_to_dict(thread: Thread) -> dict:
    """Serialize a Thread ORM object to a JSON-safe dict."""
    return {
        "id": str(thread.id),
        "subject": thread.subject,
        "message_count": thread.message_count,
        "participant_count": thread.participant_count,
        "last_message_at": (
            thread.last_message_at.isoformat() if thread.last_message_at else None
        ),
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
    }


def _thread_message_to_dict(tm: ThreadMessage) -> dict:
    """Serialize a ThreadMessage + its Message to a JSON-safe dict."""
    msg: Message = tm.message
    return {
        "id": str(tm.message_id),
        "sender_email": msg.sender_email,
        "sender_name": msg.sender_name,
        "subject": msg.subject,
        "body_text": msg.body_text,
        "body_html": msg.body_html,
        "gmail_date": msg.date.isoformat() if msg.date else None,
        "depth": tm.depth,
        "is_ghost": tm.is_ghost,
        "parent_message_id": str(tm.parent_message_id) if tm.parent_message_id else None,
    }


def create_messages_router() -> APIRouter:
    """Create an APIRouter with messages/threads endpoints.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(tags=["messages"])

    _session_dep = Depends(_get_session_dependency)

    @router.get("/api/groups/{group_id}/threads")
    async def list_threads(
        group_id: uuid.UUID,
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=20, ge=1, le=100),
        sort: str = Query(default="last_message_at_desc"),
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """List threads for a group, paginated."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        # Verify group exists and is owned by user
        group_result = await session.execute(
            select(Group).where(
                Group.id == group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = group_result.scalar_one_or_none()
        if group is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Group not found"},
            )

        # Count total threads
        count_result = await session.execute(
            select(func.count(Thread.id)).where(Thread.group_id == group_id)
        )
        total = count_result.scalar_one()

        # Build sort order
        if sort == "created_at_desc":
            order_clause = Thread.created_at.desc()
        else:
            # Default: last_message_at_desc
            order_clause = Thread.last_message_at.desc().nullslast()

        # Fetch paginated threads
        offset = (page - 1) * per_page
        threads_result = await session.execute(
            select(Thread)
            .where(Thread.group_id == group_id)
            .order_by(order_clause)
            .offset(offset)
            .limit(per_page)
        )
        threads = threads_result.scalars().all()

        return JSONResponse(
            status_code=200,
            content={
                "threads": [_thread_to_dict(t) for t in threads],
                "total": total,
                "page": page,
                "per_page": per_page,
            },
        )

    @router.get("/api/threads/{thread_id}")
    async def get_thread_detail(
        thread_id: uuid.UUID,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Get thread detail with full message hierarchy."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        # Fetch thread
        thread_result = await session.execute(
            select(Thread).where(Thread.id == thread_id)
        )
        thread = thread_result.scalar_one_or_none()
        if thread is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Thread not found"},
            )

        # Verify group ownership
        group_result = await session.execute(
            select(Group).where(
                Group.id == thread.group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = group_result.scalar_one_or_none()
        if group is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Thread not found"},
            )

        # Fetch all thread messages with their associated messages
        tms_result = await session.execute(
            select(ThreadMessage)
            .where(ThreadMessage.thread_id == thread_id)
            .options(joinedload(ThreadMessage.message))
            .order_by(ThreadMessage.position)
        )
        thread_messages = tms_result.scalars().all()

        return JSONResponse(
            status_code=200,
            content={
                "thread": _thread_to_dict(thread),
                "messages": [_thread_message_to_dict(tm) for tm in thread_messages],
            },
        )

    return router
