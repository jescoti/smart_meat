"""Tests for the Search API endpoint.

TDD RED phase — tests written before implementation.
Tests parameter validation, auth, successful search, and error handling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
THREAD_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the search router for testing."""
    from fastapi import FastAPI

    from app.api.search import _get_session_dependency, create_search_router

    app = FastAPI()
    router = create_search_router()
    app.include_router(router)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override

    return app


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_search_result(
    *,
    results: list | None = None,
    total: int = 0,
    page: int = 1,
    per_page: int = 20,
):
    """Create a SearchResult dataclass for mocking."""
    from app.services.search import SearchResult

    return SearchResult(
        results=results or [],
        total=total,
        page=page,
        per_page=per_page,
    )


def _make_search_hit(
    *,
    message_id: uuid.UUID = MESSAGE_ID_1,
    subject: str = "Test Subject",
    sender_name: str | None = "Alice",
    sender_email: str = "alice@example.com",
    gmail_date: datetime | None = None,
    snippet: str = "Test snippet...",
    group_id: uuid.UUID = GROUP_ID,
    thread_id: uuid.UUID | None = THREAD_ID,
    rank: float = 0.5,
):
    """Create a MessageSearchHit for mocking."""
    from app.services.search import MessageSearchHit

    return MessageSearchHit(
        message_id=message_id,
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        gmail_date=gmail_date or datetime(2024, 1, 12, 9, 0, tzinfo=UTC),
        snippet=snippet,
        group_id=group_id,
        thread_id=thread_id,
        rank=rank,
    )


class TestSearchEndpointAuth:
    """Tests for authentication on the search endpoint."""

    async def test_missing_user_id_returns_401(self) -> None:
        """Request without user ID should return 401."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/search?q=test")

        assert resp.status_code == 401

    async def test_user_id_from_request_state(self) -> None:
        """Auth middleware sets request.state.user_id — it should be used."""
        from fastapi import FastAPI
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        from app.api.search import _get_session_dependency, create_search_router

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self, request: Request, call_next: RequestResponseEndpoint
            ) -> Response:
                request.state.user_id = str(USER_ID)
                return await call_next(request)

        mock_session = _make_mock_session()

        app = FastAPI()
        router = create_search_router()
        app.include_router(router)
        app.add_middleware(InjectUserMiddleware)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        with patch("app.api.search.search_messages", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = _make_search_result()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/search?q=test")

        assert resp.status_code == 200


class TestSearchEndpointValidation:
    """Tests for query parameter validation."""

    async def test_missing_query_returns_400(self) -> None:
        """Request without q parameter should return 400."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 400

    async def test_empty_query_returns_400(self) -> None:
        """Request with empty q parameter should return 400."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 400

    async def test_whitespace_only_query_returns_400(self) -> None:
        """Request with whitespace-only q parameter should return 400."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=%20%20%20",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 400


class TestSearchEndpointSuccess:
    """Tests for successful search requests."""

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_successful_search_returns_200(self, mock_search: AsyncMock) -> None:
        """Valid search should return 200."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_successful_search_returns_correct_structure(
        self, mock_search: AsyncMock
    ) -> None:
        """Response should have results, total, page, per_page."""
        mock_search.return_value = _make_search_result(total=0, page=1, per_page=20)

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_search_results_serialized_correctly(self, mock_search: AsyncMock) -> None:
        """Search hits should be serialized with all expected fields."""
        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
        hit = _make_search_hit(
            message_id=MESSAGE_ID_1,
            subject="Meeting Notes",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="Notes from weekly meeting...",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.75,
        )
        mock_search.return_value = _make_search_result(results=[hit], total=1)

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=meeting",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["total"] == 1
        result = data["results"][0]
        assert result["message_id"] == str(MESSAGE_ID_1)
        assert result["subject"] == "Meeting Notes"
        assert result["sender_name"] == "Alice"
        assert result["sender_email"] == "alice@example.com"
        assert result["gmail_date"] == dt.isoformat()
        assert result["snippet"] == "Notes from weekly meeting..."
        assert result["group_id"] == str(GROUP_ID)
        assert result["thread_id"] == str(THREAD_ID)
        assert result["rank"] == 0.75

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_search_with_null_fields(self, mock_search: AsyncMock) -> None:
        """Null fields should serialize as null in JSON."""
        hit = _make_search_hit(
            sender_name=None,
            thread_id=None,
        )
        mock_search.return_value = _make_search_result(results=[hit], total=1)

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        result = data["results"][0]
        assert result["sender_name"] is None
        assert result["thread_id"] is None


class TestSearchEndpointFilters:
    """Tests for filter parameters passed to search_messages."""

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_group_id_filter_passed(self, mock_search: AsyncMock) -> None:
        """group_id query param should be passed to search_messages."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/search?q=test&group_id={GROUP_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["group_id"] == GROUP_ID

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_sender_filter_passed(self, mock_search: AsyncMock) -> None:
        """sender query param should be passed to search_messages as sender_email."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test&sender=alice@example.com",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["sender_email"] == "alice@example.com"

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_date_from_filter_passed(self, mock_search: AsyncMock) -> None:
        """date_from query param should be parsed and passed."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test&date_from=2024-01-01T00:00:00Z",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["date_from"] is not None

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_date_to_filter_passed(self, mock_search: AsyncMock) -> None:
        """date_to query param should be parsed and passed."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test&date_to=2024-12-31T23:59:59Z",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["date_to"] is not None

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_pagination_params_passed(self, mock_search: AsyncMock) -> None:
        """page and per_page query params should be passed."""
        mock_search.return_value = _make_search_result(page=2, per_page=10, total=50)

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test&page=2&per_page=10",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["page"] == 2
        assert call_kwargs.kwargs["per_page"] == 10

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_no_filters_passes_none(self, mock_search: AsyncMock) -> None:
        """When no filters are provided, None values should be passed."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=test",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200
        call_kwargs = mock_search.call_args
        assert call_kwargs.kwargs["group_id"] is None
        assert call_kwargs.kwargs["sender_email"] is None
        assert call_kwargs.kwargs["date_from"] is None
        assert call_kwargs.kwargs["date_to"] is None


class TestSearchEndpointEmptyResults:
    """Tests for empty search results."""

    @patch("app.api.search.search_messages", new_callable=AsyncMock)
    async def test_empty_results_returns_empty_list(self, mock_search: AsyncMock) -> None:
        """No matches should return an empty results list."""
        mock_search.return_value = _make_search_result()

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/search?q=nonexistent",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0
