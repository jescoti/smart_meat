"""Group management API endpoints.

Provides CRUD for Google Groups, sync trigger, and sync status polling.
Uses the same factory-router pattern as the auth router for testability.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Group, GroupSyncStatus


class CreateGroupRequest(BaseModel):
    """Request body for creating a new group."""

    gmail_group_email: str


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


def _get_user_id(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> str | None:
    """Extract user_id from request state (auth middleware) or X-User-Id header (testing)."""
    # Prefer request.state.user_id set by auth middleware
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return str(user_id)
    # Fall back to X-User-Id header for testing
    return x_user_id


def _group_to_dict(group: Group) -> dict:
    """Serialize a Group ORM object to a JSON-safe dict."""
    return {
        "id": str(group.id),
        "owner_id": str(group.owner_id),
        "gmail_group_email": group.google_group_email,
        "display_name": group.display_name,
        "sync_status": (
            group.sync_status.value
            if hasattr(group.sync_status, "value")
            else str(group.sync_status)
        ),
        "sync_error_message": group.sync_error_message,
        "sync_progress_current": group.sync_progress_current,
        "sync_progress_total": group.sync_progress_total,
        "gmail_history_id": group.gmail_history_id,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "updated_at": group.updated_at.isoformat() if group.updated_at else None,
    }


def create_groups_router(
    *,
    encryption_key: str,
    google_client_id: str,
    google_client_secret: str,
) -> APIRouter:
    """Create an APIRouter with group management endpoints.

    Args:
        encryption_key: Key for AES-256-GCM encryption of Google tokens.
        google_client_id: Google OAuth client ID (for token refresh).
        google_client_secret: Google OAuth client secret (for token refresh).

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(prefix="/api/groups", tags=["groups"])

    _session_dep = Depends(_get_session_dependency)

    @router.post("")
    async def create_group(
        body: CreateGroupRequest,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Add a new group for the authenticated user."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        group = Group(
            owner_id=uuid.UUID(user_id),
            google_group_email=body.gmail_group_email,
            display_name=body.gmail_group_email,
            sync_status=GroupSyncStatus.idle,
        )
        session.add(group)

        audit_entry = AuditLog(
            user_id=uuid.UUID(user_id),
            action="group_added",
            resource_type="group",
            resource_id=str(group.id),
        )
        session.add(audit_entry)
        await session.commit()
        await session.refresh(group)

        return JSONResponse(
            status_code=201,
            content=_group_to_dict(group),
        )

    @router.get("")
    async def list_groups(
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """List all groups for the authenticated user."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        result = await session.execute(
            select(Group).where(Group.owner_id == uuid.UUID(user_id))
        )
        groups = result.scalars().all()

        return JSONResponse(
            status_code=200,
            content=[_group_to_dict(g) for g in groups],
        )

    @router.get("/{group_id}")
    async def get_group(
        group_id: uuid.UUID,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Get details for a specific group."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        result = await session.execute(
            select(Group).where(
                Group.id == group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = result.scalar_one_or_none()

        if group is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Group not found"},
            )

        return JSONResponse(status_code=200, content=_group_to_dict(group))

    @router.post("/{group_id}/sync")
    async def trigger_sync(
        group_id: uuid.UUID,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Trigger sync for a group.

        Sets sync_status to 'syncing' and records an audit log entry.
        In a production setup, this would dispatch a Celery task.
        """
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        result = await session.execute(
            select(Group).where(
                Group.id == group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = result.scalar_one_or_none()

        if group is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Group not found"},
            )

        group.sync_status = GroupSyncStatus.syncing
        group.sync_error_message = None

        audit_entry = AuditLog(
            user_id=uuid.UUID(user_id),
            action="sync_trigger",
            resource_type="group",
            resource_id=str(group_id),
        )
        session.add(audit_entry)
        await session.commit()

        return JSONResponse(
            status_code=202,
            content={"status": "syncing", "group_id": str(group_id)},
        )

    @router.get("/{group_id}/sync-status")
    async def get_sync_status(
        group_id: uuid.UUID,
        session: AsyncSession = _session_dep,
        user_id: str | None = Depends(_get_user_id),
    ) -> JSONResponse:
        """Get the current sync status and progress for a group."""
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing user ID"},
            )

        result = await session.execute(
            select(Group).where(
                Group.id == group_id,
                Group.owner_id == uuid.UUID(user_id),
            )
        )
        group = result.scalar_one_or_none()

        if group is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "Group not found"},
            )

        status_value = (
            group.sync_status.value
            if hasattr(group.sync_status, "value")
            else str(group.sync_status)
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": status_value,
                "progress_current": group.sync_progress_current,
                "progress_total": group.sync_progress_total,
                "error_message": group.sync_error_message,
            },
        )

    return router
