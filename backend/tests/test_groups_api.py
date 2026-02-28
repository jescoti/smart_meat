"""Tests for the Group API endpoints.

TDD RED phase — tests written before implementation.
Tests all group CRUD endpoints, sync trigger, sync status, and audit logging.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.db.models import GroupSyncStatus

# Test constants
SECRET_KEY = "test-secret-key-at-least-32-chars-long!"
ENCRYPTION_KEY = "test-encryption-key"
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")


async def _get_session_stub() -> None:  # pragma: no cover
    """Placeholder dependency — overridden in tests."""
    raise NotImplementedError


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the groups router for testing."""
    from fastapi import FastAPI

    from app.api.groups import _get_session_dependency, create_groups_router

    app = FastAPI()
    router = create_groups_router(
        encryption_key=ENCRYPTION_KEY,
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
    )
    app.include_router(router)

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
    session.refresh = AsyncMock()
    return session


def _make_mock_group(
    *,
    group_id: uuid.UUID = GROUP_ID,
    owner_id: uuid.UUID = USER_ID,
    google_group_email: str = "test-group@googlegroups.com",
    display_name: str = "test-group@googlegroups.com",
    sync_status: GroupSyncStatus = GroupSyncStatus.idle,
    sync_error_message: str | None = None,
    sync_progress_current: int | None = None,
    sync_progress_total: int | None = None,
    gmail_history_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Group ORM object."""
    group = MagicMock()
    group.id = group_id
    group.owner_id = owner_id
    group.google_group_email = google_group_email
    group.display_name = display_name
    group.sync_status = sync_status
    group.sync_error_message = sync_error_message
    group.sync_progress_current = sync_progress_current
    group.sync_progress_total = sync_progress_total
    group.gmail_history_id = gmail_history_id
    group.created_at = created_at or datetime.now(tz=UTC)
    group.updated_at = updated_at or datetime.now(tz=UTC)
    group.auto_extract_nuggets = False
    return group


def _auth_cookies() -> dict[str, str]:
    """Return a dict with a valid access_token cookie."""
    token = create_access_token(str(USER_ID), SECRET_KEY)
    return {"access_token": token}


class TestCreateGroup:
    """Tests for POST /api/groups."""

    async def test_create_group_returns_201(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_session.refresh = AsyncMock(side_effect=lambda g: None)

        # Make session.add capture the group
        added_objects: list[object] = []

        def capture_add(obj: object) -> None:
            added_objects.append(obj)

        mock_session.add = MagicMock(side_effect=capture_add)

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Inject user_id via a custom middleware since auth middleware isn't mounted
            resp = await client.post(
                "/api/groups",
                json={"gmail_group_email": "test-group@googlegroups.com"},
                cookies=_auth_cookies(),
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 201

    async def test_create_group_returns_group_data(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/groups",
                json={"gmail_group_email": "test-group@googlegroups.com"},
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["gmail_group_email"] == "test-group@googlegroups.com"
        assert data["sync_status"] == "idle"

    async def test_create_group_records_audit_log(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/groups",
                json={"gmail_group_email": "test-group@googlegroups.com"},
                headers={"X-User-Id": str(USER_ID)},
            )

        # Check that session.add was called at least twice (group + audit log)
        assert mock_session.add.call_count >= 2

    async def test_create_group_missing_email_returns_422(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/groups",
                json={},
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 422

    async def test_create_group_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/groups",
                json={"gmail_group_email": "test-group@googlegroups.com"},
            )

        assert resp.status_code == 401


class TestGetUserIdFromState:
    """Tests for _get_user_id when request.state.user_id is set (auth middleware path)."""

    async def test_user_id_from_request_state(self) -> None:
        """When auth middleware sets request.state.user_id, it should be used."""
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        from fastapi import FastAPI

        from app.api.groups import _get_session_dependency, create_groups_router

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
                request.state.user_id = str(USER_ID)
                return await call_next(request)

        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        app = FastAPI()
        router = create_groups_router(
            encryption_key=ENCRYPTION_KEY,
            google_client_id="test-client-id",
            google_client_secret="test-client-secret",
        )
        app.include_router(router)
        app.add_middleware(InjectUserMiddleware)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/groups")

        assert resp.status_code == 200


class TestListGroups:
    """Tests for GET /api/groups."""

    async def test_list_groups_returns_200(self) -> None:
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/groups",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_list_groups_returns_array(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_group]
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/groups",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

    async def test_list_groups_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/groups")

        assert resp.status_code == 401


class TestGetGroup:
    """Tests for GET /api/groups/{group_id}."""

    async def test_get_group_returns_200(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_get_group_returns_group_data(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["id"] == str(GROUP_ID)
        assert data["gmail_group_email"] == "test-group@googlegroups.com"

    async def test_get_group_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_get_group_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/groups/{GROUP_ID}")

        assert resp.status_code == 401


class TestTriggerSync:
    """Tests for POST /api/groups/{group_id}/sync."""

    async def test_trigger_sync_returns_202(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/groups/{GROUP_ID}/sync",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 202

    async def test_trigger_sync_sets_syncing_status(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/groups/{GROUP_ID}/sync",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["status"] == "syncing"

    async def test_trigger_sync_records_audit_log(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/groups/{GROUP_ID}/sync",
                headers={"X-User-Id": str(USER_ID)},
            )

        # session.add should have been called for the audit log
        assert mock_session.add.call_count >= 1

    async def test_trigger_sync_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/groups/{GROUP_ID}/sync",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_trigger_sync_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/groups/{GROUP_ID}/sync")

        assert resp.status_code == 401


class TestSyncStatus:
    """Tests for GET /api/groups/{group_id}/sync-status."""

    async def test_sync_status_returns_200(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group(
            sync_status=GroupSyncStatus.syncing,
            sync_progress_current=10,
            sync_progress_total=100,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/sync-status",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_sync_status_returns_progress(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group(
            sync_status=GroupSyncStatus.syncing,
            sync_progress_current=10,
            sync_progress_total=100,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/sync-status",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["status"] == "syncing"
        assert data["progress_current"] == 10
        assert data["progress_total"] == 100
        assert data["error_message"] is None

    async def test_sync_status_with_error(self) -> None:
        mock_session = _make_mock_session()
        mock_group = _make_mock_group(
            sync_status=GroupSyncStatus.error,
            sync_error_message="Rate limited",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/sync-status",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["status"] == "error"
        assert data["error_message"] == "Rate limited"

    async def test_sync_status_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/sync-status",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_sync_status_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/groups/{GROUP_ID}/sync-status")

        assert resp.status_code == 401
