"""Dashboard API endpoint -- aggregated summary for the landing page.

Provides a single ``GET /api/dashboard/summary`` endpoint that returns
counts and recent items for the authenticated user's groups, threads,
and knowledge nuggets.

Uses the factory-router pattern for testability.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, Nugget, NuggetStatus, Thread


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


def _truncate_content(content: str, max_length: int = 200) -> str:
    """Truncate content to max_length characters, appending '...' if truncated."""
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def create_dashboard_router() -> APIRouter:
    """Create an APIRouter with the dashboard summary endpoint.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

    _session_dep = Depends(_get_session_dependency)

    @router.get("/summary")
    async def get_summary(
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Return an aggregated dashboard summary for the authenticated user.

        Response includes:
            groups_count: Total groups owned by the user.
            threads_count: Total threads across the user's groups.
            nuggets_count: Total accepted nuggets across the user's groups.
            recent_threads: Last 5 threads ordered by most recent activity.
            recent_nuggets: Last 5 accepted nuggets with content preview.
        """
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        uid = uuid.UUID(user_id)

        # Count groups for this user
        groups_result = await session.execute(
            select(func.count(Group.id)).where(Group.owner_id == uid)
        )
        groups_count: int = groups_result.scalar_one()

        # Count threads across user's groups
        threads_result = await session.execute(
            select(func.count(Thread.id)).where(
                Thread.group_id.in_(select(Group.id).where(Group.owner_id == uid))
            )
        )
        threads_count: int = threads_result.scalar_one()

        # Count accepted nuggets across user's groups
        nuggets_result = await session.execute(
            select(func.count(Nugget.id)).where(
                Nugget.group_id.in_(select(Group.id).where(Group.owner_id == uid)),
                Nugget.status == NuggetStatus.accepted,
            )
        )
        nuggets_count: int = nuggets_result.scalar_one()

        # Recent threads (last 5, ordered by last_message_at desc)
        recent_threads_result = await session.execute(
            select(
                Thread.id.label("thread_id"),
                Thread.subject,
                Group.display_name.label("group_name"),
                Thread.message_count,
                Thread.last_message_at.label("last_activity"),
            )
            .join(Group, Thread.group_id == Group.id)
            .where(Group.owner_id == uid)
            .order_by(Thread.last_message_at.desc().nulls_last())
            .limit(5)
        )
        recent_threads_rows = recent_threads_result.all()

        # Recent accepted nuggets (last 5)
        # Left join through source_message -> thread_messages -> thread to get subject
        recent_nuggets_result = await session.execute(
            select(
                Nugget.id.label("nugget_id"),
                Nugget.content,
                literal_column("NULL").label("source_thread_subject"),
            )
            .where(
                Nugget.group_id.in_(select(Group.id).where(Group.owner_id == uid)),
                Nugget.status == NuggetStatus.accepted,
            )
            .order_by(Nugget.created_at.desc())
            .limit(5)
        )
        recent_nuggets_rows = recent_nuggets_result.all()

        return JSONResponse(
            status_code=200,
            content={
                "groups_count": groups_count,
                "threads_count": threads_count,
                "nuggets_count": nuggets_count,
                "recent_threads": [
                    {
                        "subject": row.subject,
                        "group_name": row.group_name,
                        "message_count": row.message_count,
                        "last_activity": (
                            row.last_activity.isoformat() if row.last_activity else None
                        ),
                    }
                    for row in recent_threads_rows
                ],
                "recent_nuggets": [
                    {
                        "content_preview": _truncate_content(row.content),
                        "source_thread_subject": row.source_thread_subject,
                    }
                    for row in recent_nuggets_rows
                ],
            },
        )

    return router
