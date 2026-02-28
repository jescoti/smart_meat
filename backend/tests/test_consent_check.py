"""Tests for the require_llm_consent FastAPI dependency.

TDD RED phase -- these tests are written before the implementation.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token

# Test constants
SECRET_KEY = "test-secret-key-at-least-32-chars-long!"
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_mock_user(
    *,
    user_id: uuid.UUID = USER_ID,
    llm_consent_given_at: datetime | None = None,
) -> MagicMock:
    """Create a mock User ORM object."""
    user = MagicMock()
    user.id = user_id
    user.llm_consent_given_at = llm_consent_given_at
    return user


def _make_auth_cookie() -> str:
    """Create a valid JWT access token cookie value."""
    return create_access_token(str(USER_ID), SECRET_KEY)


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with a test route that uses require_llm_consent."""
    from fastapi import Depends, FastAPI

    from app.middleware.auth import AuthMiddleware
    from app.middleware.consent import _get_session_dependency, require_llm_consent

    app = FastAPI()

    @app.get("/api/llm-feature")
    async def llm_feature(
        _consent: None = Depends(require_llm_consent),
    ) -> dict[str, str]:
        return {"status": "ok"}

    # Add auth middleware so user_id is set on request.state
    app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override

    return app


class TestRequireLlmConsent:
    """Tests for the require_llm_consent dependency."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/llm-feature")
        assert resp.status_code == 401

    async def test_no_consent_returns_403(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user(llm_consent_given_at=None)
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/llm-feature")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "LLM consent required"

    async def test_with_consent_passes(self) -> None:
        now = datetime.now(tz=UTC)
        mock_session = _make_mock_session()
        mock_user = _make_mock_user(llm_consent_given_at=now)
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/llm-feature")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_user_not_found_returns_403(self) -> None:
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/llm-feature")

        assert resp.status_code == 403
        assert resp.json()["detail"] == "LLM consent required"
