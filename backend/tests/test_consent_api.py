"""Tests for the consent API endpoints.

TDD RED phase -- these tests are written before the implementation.
All database operations are mocked via mock sessions.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token

# Test constants
SECRET_KEY = "test-secret-key-at-least-32-chars-long!"
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


async def _get_session_stub() -> None:  # pragma: no cover
    """Placeholder — overridden in tests."""
    raise NotImplementedError


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the consent router for testing."""
    from fastapi import FastAPI

    from app.api.consent import _get_session_dependency, create_consent_router
    from app.middleware.auth import AuthMiddleware

    app = FastAPI()

    router = create_consent_router()
    app.include_router(router)

    # Add auth middleware so user_id is set on request.state
    app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override

    return app


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
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


class TestGrantConsent:
    """Tests for POST /api/consent."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/consent")
        assert resp.status_code == 401

    async def test_grant_consent_returns_200(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.post("/api/consent")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_grant_consent_sets_timestamp(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            await client.post("/api/consent")

        # The user's llm_consent_given_at should have been set
        assert mock_user.llm_consent_given_at is not None
        assert isinstance(mock_user.llm_consent_given_at, datetime)

    async def test_grant_consent_creates_audit_log(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            await client.post("/api/consent")

        # session.add should have been called with an AuditLog
        assert mock_session.add.called
        audit_log = mock_session.add.call_args[0][0]
        assert audit_log.action == "consent_granted"
        assert audit_log.user_id == USER_ID
        assert audit_log.resource_type == "consent"
        assert audit_log.resource_id == str(USER_ID)

    async def test_grant_consent_user_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.post("/api/consent")

        assert resp.status_code == 404

    async def test_grant_consent_commits_session(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            await client.post("/api/consent")

        assert mock_session.commit.called


class TestRevokeConsent:
    """Tests for DELETE /api/consent."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/consent")
        assert resp.status_code == 401

    async def test_revoke_consent_returns_200(self) -> None:
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
            resp = await client.delete("/api/consent")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_revoke_consent_clears_timestamp(self) -> None:
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
            await client.delete("/api/consent")

        assert mock_user.llm_consent_given_at is None

    async def test_revoke_consent_creates_audit_log(self) -> None:
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
            await client.delete("/api/consent")

        assert mock_session.add.called
        audit_log = mock_session.add.call_args[0][0]
        assert audit_log.action == "consent_revoked"
        assert audit_log.user_id == USER_ID
        assert audit_log.resource_type == "consent"
        assert audit_log.resource_id == str(USER_ID)

    async def test_revoke_consent_user_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.delete("/api/consent")

        assert resp.status_code == 404

    async def test_revoke_consent_commits_session(self) -> None:
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
            await client.delete("/api/consent")

        assert mock_session.commit.called


class TestGetConsentStatus:
    """Tests for GET /api/consent."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/consent")
        assert resp.status_code == 401

    async def test_returns_false_when_no_consent(self) -> None:
        mock_session = _make_mock_session()
        mock_user = _make_mock_user(llm_consent_given_at=None)
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/consent")

        assert resp.status_code == 200
        data = resp.json()
        assert data["consented"] is False
        assert data["consented_at"] is None

    async def test_returns_true_when_consented(self) -> None:
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        mock_session = _make_mock_session()
        mock_user = _make_mock_user(llm_consent_given_at=now)
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/consent")

        assert resp.status_code == 200
        data = resp.json()
        assert data["consented"] is True
        assert data["consented_at"] == "2024-06-15T12:00:00+00:00"

    async def test_user_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/consent")

        assert resp.status_code == 404
