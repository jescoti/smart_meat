"""Tests for the Dashboard API endpoint.

TDD RED phase -- tests written before implementation.
Tests the /api/dashboard/summary endpoint for correct structure,
empty state, populated state, ordering, and limits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID_1 = uuid.UUID("660e8400-e29b-41d4-a716-446655440001")
GROUP_ID_2 = uuid.UUID("660e8400-e29b-41d4-a716-446655440002")
THREAD_ID_1 = uuid.UUID("770e8400-e29b-41d4-a716-446655440001")
THREAD_ID_2 = uuid.UUID("770e8400-e29b-41d4-a716-446655440002")
NUGGET_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
NUGGET_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the dashboard router for testing."""
    from fastapi import FastAPI

    from app.api.dashboard import _get_session_dependency, create_dashboard_router

    app = FastAPI()
    router = create_dashboard_router()
    app.include_router(router)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override

    return app


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_scalar_one_result(value: int) -> MagicMock:
    """Create a mock result with scalar_one() returning an int."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_all_result(rows: list) -> MagicMock:
    """Create a mock result with all() returning a list of rows."""
    result = MagicMock()
    result.all.return_value = rows
    return result


def _make_thread_row(
    *,
    thread_id: uuid.UUID = THREAD_ID_1,
    subject: str = "Test Thread",
    group_name: str = "Test Group",
    message_count: int = 5,
    last_activity: datetime | None = None,
) -> MagicMock:
    """Create a mock row for a recent thread."""
    row = MagicMock()
    row.thread_id = thread_id
    row.subject = subject
    row.group_name = group_name
    row.message_count = message_count
    row.last_activity = last_activity or datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
    return row


def _make_nugget_row(
    *,
    nugget_id: uuid.UUID = NUGGET_ID_1,
    content: str = "This is a knowledge nugget about testing best practices.",
    source_thread_subject: str = "Testing Discussion",
) -> MagicMock:
    """Create a mock row for a recent nugget."""
    row = MagicMock()
    row.nugget_id = nugget_id
    row.content = content
    row.source_thread_subject = source_thread_subject
    return row


class TestDashboardSummaryAuth:
    """Tests for authentication on the dashboard summary endpoint."""

    async def test_missing_user_id_returns_401(self) -> None:
        """Request without user ID should return 401."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/dashboard/summary")

        assert resp.status_code == 401

    async def test_user_id_from_header_returns_200(self) -> None:
        """X-User-Id header should be accepted for auth."""
        mock_session = _make_mock_session()

        # Set up mock responses for the 5 queries
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(0),  # groups_count
                _make_scalar_one_result(0),  # threads_count
                _make_scalar_one_result(0),  # nuggets_count
                _make_all_result([]),  # recent_threads
                _make_all_result([]),  # recent_nuggets
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_user_id_from_request_state(self) -> None:
        """Auth middleware sets request.state.user_id -- it should be used."""
        from fastapi import FastAPI
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        from app.api.dashboard import _get_session_dependency, create_dashboard_router

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self, request: Request, call_next: RequestResponseEndpoint
            ) -> Response:
                request.state.user_id = str(USER_ID)
                return await call_next(request)

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_all_result([]),
                _make_all_result([]),
            ]
        )

        app = FastAPI()
        router = create_dashboard_router()
        app.include_router(router)
        app.add_middleware(InjectUserMiddleware)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/dashboard/summary")

        assert resp.status_code == 200


class TestDashboardSummaryStructure:
    """Tests for the response structure of the dashboard summary."""

    async def test_returns_correct_keys(self) -> None:
        """Response should contain all required top-level keys."""
        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_all_result([]),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert "groups_count" in data
        assert "threads_count" in data
        assert "nuggets_count" in data
        assert "recent_threads" in data
        assert "recent_nuggets" in data


class TestDashboardSummaryEmpty:
    """Tests for empty state (no groups, threads, nuggets)."""

    async def test_empty_state_returns_zero_counts(self) -> None:
        """When user has no data, all counts should be 0."""
        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_scalar_one_result(0),
                _make_all_result([]),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["groups_count"] == 0
        assert data["threads_count"] == 0
        assert data["nuggets_count"] == 0
        assert data["recent_threads"] == []
        assert data["recent_nuggets"] == []


class TestDashboardSummaryCounts:
    """Tests for accurate counts in the dashboard summary."""

    async def test_counts_reflect_data(self) -> None:
        """Counts should reflect the actual data for the user."""
        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(3),   # groups_count
                _make_scalar_one_result(25),  # threads_count
                _make_scalar_one_result(12),  # nuggets_count
                _make_all_result([]),  # recent_threads
                _make_all_result([]),  # recent_nuggets
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["groups_count"] == 3
        assert data["threads_count"] == 25
        assert data["nuggets_count"] == 12


class TestDashboardSummaryRecentThreads:
    """Tests for recent threads in the dashboard summary."""

    async def test_recent_threads_structure(self) -> None:
        """Each recent thread should have subject, group_name, message_count, last_activity."""
        dt = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
        thread_row = _make_thread_row(
            thread_id=THREAD_ID_1,
            subject="Weekly Meeting Notes",
            group_name="Engineering",
            message_count=10,
            last_activity=dt,
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(0),
                _make_all_result([thread_row]),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert len(data["recent_threads"]) == 1
        thread = data["recent_threads"][0]
        assert thread["subject"] == "Weekly Meeting Notes"
        assert thread["group_name"] == "Engineering"
        assert thread["message_count"] == 10
        assert thread["last_activity"] == dt.isoformat()

    async def test_recent_threads_limited_to_5(self) -> None:
        """Recent threads should be limited to 5 items."""
        threads = [
            _make_thread_row(
                thread_id=uuid.uuid4(),
                subject=f"Thread {i}",
                group_name="Test Group",
                message_count=i,
                last_activity=datetime(2024, 6, i + 1, 12, 0, tzinfo=UTC),
            )
            for i in range(5)
        ]

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(5),
                _make_scalar_one_result(0),
                _make_all_result(threads),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert len(data["recent_threads"]) == 5

    async def test_recent_threads_ordered_most_recent_first(self) -> None:
        """Recent threads should be ordered by most recent first."""
        older = _make_thread_row(
            thread_id=THREAD_ID_1,
            subject="Older Thread",
            last_activity=datetime(2024, 6, 1, 12, 0, tzinfo=UTC),
        )
        newer = _make_thread_row(
            thread_id=THREAD_ID_2,
            subject="Newer Thread",
            last_activity=datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
        )

        mock_session = _make_mock_session()
        # The endpoint should request ordered by most recent;
        # we return them in that order as the DB would
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(2),
                _make_scalar_one_result(0),
                _make_all_result([newer, older]),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert len(data["recent_threads"]) == 2
        assert data["recent_threads"][0]["subject"] == "Newer Thread"
        assert data["recent_threads"][1]["subject"] == "Older Thread"


class TestDashboardSummaryRecentNuggets:
    """Tests for recent nuggets in the dashboard summary."""

    async def test_recent_nuggets_structure(self) -> None:
        """Each recent nugget should have content_preview and source_thread_subject."""
        nugget_row = _make_nugget_row(
            nugget_id=NUGGET_ID_1,
            content="Testing best practices include writing tests first.",
            source_thread_subject="Testing Discussion",
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_all_result([]),
                _make_all_result([nugget_row]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert len(data["recent_nuggets"]) == 1
        nugget = data["recent_nuggets"][0]
        assert "content_preview" in nugget
        assert nugget["source_thread_subject"] == "Testing Discussion"

    async def test_recent_nuggets_limited_to_5(self) -> None:
        """Recent nuggets should be limited to 5 items."""
        nuggets = [
            _make_nugget_row(
                nugget_id=uuid.uuid4(),
                content=f"Nugget content {i}",
                source_thread_subject=f"Thread {i}",
            )
            for i in range(5)
        ]

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(5),
                _make_all_result([]),
                _make_all_result(nuggets),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert len(data["recent_nuggets"]) == 5

    async def test_content_preview_truncated(self) -> None:
        """Long content should be truncated in the content_preview field."""
        long_content = "A" * 300
        nugget_row = _make_nugget_row(
            nugget_id=NUGGET_ID_1,
            content=long_content,
            source_thread_subject="Long Content Thread",
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_all_result([]),
                _make_all_result([nugget_row]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        nugget = data["recent_nuggets"][0]
        # Content preview should be truncated to 200 chars + "..."
        assert len(nugget["content_preview"]) <= 203

    async def test_short_content_not_truncated(self) -> None:
        """Short content should not be truncated."""
        short_content = "Short nugget content."
        nugget_row = _make_nugget_row(
            nugget_id=NUGGET_ID_1,
            content=short_content,
            source_thread_subject="Short Thread",
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_all_result([]),
                _make_all_result([nugget_row]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        nugget = data["recent_nuggets"][0]
        assert nugget["content_preview"] == short_content

    async def test_nugget_with_null_source_thread_subject(self) -> None:
        """Nuggets without a source thread should have null source_thread_subject."""
        nugget_row = _make_nugget_row(
            nugget_id=NUGGET_ID_1,
            content="Manual nugget content.",
            source_thread_subject=None,
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_all_result([]),
                _make_all_result([nugget_row]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        nugget = data["recent_nuggets"][0]
        assert nugget["source_thread_subject"] is None


class TestDashboardSummaryFullData:
    """Tests for dashboard with full data present."""

    async def test_full_summary_with_data(self) -> None:
        """Summary should include all data when user has groups, threads, and nuggets."""
        thread_row = _make_thread_row(
            thread_id=THREAD_ID_1,
            subject="Project Update",
            group_name="Engineering",
            message_count=7,
            last_activity=datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
        )
        nugget_row = _make_nugget_row(
            nugget_id=NUGGET_ID_1,
            content="Key insight from discussion.",
            source_thread_subject="Architecture Review",
        )

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(2),   # groups_count
                _make_scalar_one_result(15),  # threads_count
                _make_scalar_one_result(8),   # nuggets_count
                _make_all_result([thread_row]),
                _make_all_result([nugget_row]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["groups_count"] == 2
        assert data["threads_count"] == 15
        assert data["nuggets_count"] == 8
        assert len(data["recent_threads"]) == 1
        assert data["recent_threads"][0]["subject"] == "Project Update"
        assert len(data["recent_nuggets"]) == 1
        assert data["recent_nuggets"][0]["source_thread_subject"] == "Architecture Review"

    async def test_thread_with_null_last_activity(self) -> None:
        """Threads with null last_activity should serialize as null."""
        thread_row = _make_thread_row(
            thread_id=THREAD_ID_1,
            subject="Empty Thread",
            group_name="Test Group",
            message_count=0,
        )
        thread_row.last_activity = None

        mock_session = _make_mock_session()
        mock_session.execute = AsyncMock(
            side_effect=[
                _make_scalar_one_result(1),
                _make_scalar_one_result(1),
                _make_scalar_one_result(0),
                _make_all_result([thread_row]),
                _make_all_result([]),
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/dashboard/summary",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        thread = data["recent_threads"][0]
        assert thread["last_activity"] is None
