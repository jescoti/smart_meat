"""LLM consent check dependency for FastAPI.

Provides ``require_llm_consent`` which can be used as a FastAPI dependency
on any LLM-dependent endpoint.  It checks if the authenticated user has
granted LLM consent (``llm_consent_given_at`` is set).  If not, a 403
response is returned.

This is NOT a middleware -- it is a per-route dependency that individual
routes opt into via ``Depends(require_llm_consent)``.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency -- overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


async def require_llm_consent(
    request: Request,
    session: AsyncSession = Depends(_get_session_dependency),
) -> None:
    """FastAPI dependency that enforces LLM consent.

    Checks if the authenticated user (identified by ``request.state.user_id``)
    has a non-null ``llm_consent_given_at`` timestamp.  If not, raises an
    HTTP 403 error.

    Usage::

        @app.get("/api/llm-feature")
        async def llm_feature(
            _consent: None = Depends(require_llm_consent),
        ):
            ...
    """
    user_id = request.state.user_id

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or user.llm_consent_given_at is None:
        raise HTTPException(status_code=403, detail="LLM consent required")
