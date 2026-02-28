"""Consent API endpoints for LLM processing opt-in.

Provides endpoints to grant, revoke, and check LLM consent status.
The router is created via ``create_consent_router()`` following the same
factory pattern used by the auth router.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


def create_consent_router() -> APIRouter:
    """Create an APIRouter with consent management endpoints.

    Returns:
        A configured FastAPI APIRouter with consent endpoints.
    """
    router = APIRouter(prefix="/api/consent", tags=["consent"])

    _session_dep = Depends(_get_session_dependency)

    @router.post("")
    async def grant_consent(
        request: Request,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Record LLM consent for the authenticated user.

        Sets ``llm_consent_given_at`` to the current UTC timestamp and
        creates an audit log entry with action ``consent_granted``.
        """
        user_id = request.state.user_id

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "User not found"},
            )

        user.llm_consent_given_at = datetime.now(tz=UTC)

        audit_entry = AuditLog(
            user_id=user.id,
            action="consent_granted",
            resource_type="consent",
            resource_id=str(user.id),
            ip_address=None,
        )
        session.add(audit_entry)
        await session.commit()

        return JSONResponse(status_code=200, content={"status": "ok"})

    @router.delete("")
    async def revoke_consent(
        request: Request,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Revoke LLM consent for the authenticated user.

        Sets ``llm_consent_given_at`` to ``None`` and creates an audit log
        entry with action ``consent_revoked``.
        """
        user_id = request.state.user_id

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "User not found"},
            )

        user.llm_consent_given_at = None

        audit_entry = AuditLog(
            user_id=user.id,
            action="consent_revoked",
            resource_type="consent",
            resource_id=str(user.id),
            ip_address=None,
        )
        session.add(audit_entry)
        await session.commit()

        return JSONResponse(status_code=200, content={"status": "ok"})

    @router.get("")
    async def get_consent_status(
        request: Request,
        session: AsyncSession = _session_dep,
    ) -> JSONResponse:
        """Return the current LLM consent status for the authenticated user.

        Returns a JSON object with ``consented`` (bool) and ``consented_at``
        (ISO 8601 timestamp string or null).
        """
        user_id = request.state.user_id

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "User not found"},
            )

        consented = user.llm_consent_given_at is not None
        consented_at = (
            user.llm_consent_given_at.isoformat() if user.llm_consent_given_at else None
        )

        return JSONResponse(
            status_code=200,
            content={
                "consented": consented,
                "consented_at": consented_at,
            },
        )

    return router
