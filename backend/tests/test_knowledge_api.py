"""Tests for the knowledge API endpoints.

TDD RED phase -- these tests are written before the implementation.
All database and service operations are mocked.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.db.models import NuggetSourceType, NuggetStatus

# Test constants
SECRET_KEY = "test-secret-key-at-least-32-chars-long!"
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440001")
NUGGET_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440002")
THREAD_ID = uuid.UUID("880e8400-e29b-41d4-a716-446655440003")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the knowledge router for testing."""
    from fastapi import FastAPI

    from app.api.knowledge import _get_session_dependency, create_knowledge_router
    from app.middleware.auth import AuthMiddleware
    from app.middleware.consent import (
        _get_session_dependency as _consent_session_dep,
    )

    app = FastAPI()

    router = create_knowledge_router()
    app.include_router(router)

    app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override
        # The require_llm_consent dependency uses its own session dependency
        app.dependency_overrides[_consent_session_dep] = lambda: session_override

    return app


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _make_auth_cookie() -> str:
    """Create a valid JWT access token cookie value."""
    return create_access_token(str(USER_ID), SECRET_KEY)


def _make_mock_nugget(
    *,
    nugget_id: uuid.UUID = NUGGET_ID,
    status: NuggetStatus = NuggetStatus.accepted,
    source_type: NuggetSourceType = NuggetSourceType.manual,
) -> MagicMock:
    """Create a mock Nugget ORM object."""
    nugget = MagicMock()
    nugget.id = nugget_id
    nugget.group_id = GROUP_ID
    nugget.source_message_id = None
    nugget.title = "Test Nugget"
    nugget.content = "Test content"
    nugget.tags = ["test"]
    nugget.source_type = source_type
    nugget.status = status
    nugget.created_by = USER_ID
    nugget.created_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    nugget.updated_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    return nugget


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


# ---------------------------------------------------------------------------
# GET /api/knowledge/nuggets — list nuggets
# ---------------------------------------------------------------------------


class TestListNuggets:
    """Tests for GET /api/knowledge/nuggets."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/knowledge/nuggets")
        assert resp.status_code == 401

    async def test_returns_200_with_nuggets(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget()

        with patch("app.api.knowledge.list_nuggets", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([mock_nugget], 1)
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.get(
                    f"/api/knowledge/nuggets?group_id={GROUP_ID}"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["nuggets"]) == 1
        assert data["nuggets"][0]["title"] == "Test Nugget"

    async def test_requires_group_id(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.get("/api/knowledge/nuggets")
        assert resp.status_code == 422

    async def test_filters_by_status(self) -> None:
        mock_session = _make_mock_session()
        with patch("app.api.knowledge.list_nuggets", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.get(
                    f"/api/knowledge/nuggets?group_id={GROUP_ID}&status=suggested"
                )
        assert resp.status_code == 200

    async def test_pagination_params(self) -> None:
        mock_session = _make_mock_session()
        with patch("app.api.knowledge.list_nuggets", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ([], 0)
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.get(
                    f"/api/knowledge/nuggets?group_id={GROUP_ID}&page=2&per_page=10"
                )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/knowledge/nuggets/{nugget_id} — get nugget detail
# ---------------------------------------------------------------------------


class TestGetNugget:
    """Tests for GET /api/knowledge/nuggets/{nugget_id}."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/knowledge/nuggets/{NUGGET_ID}")
        assert resp.status_code == 401

    async def test_returns_200_with_nugget(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget()

        with patch("app.api.knowledge.get_nugget", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.get(f"/api/knowledge/nuggets/{NUGGET_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(NUGGET_ID)
        assert data["title"] == "Test Nugget"

    async def test_returns_404_when_not_found(self) -> None:
        mock_session = _make_mock_session()
        with patch("app.api.knowledge.get_nugget", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.get(f"/api/knowledge/nuggets/{NUGGET_ID}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/knowledge/nuggets — create manual nugget
# ---------------------------------------------------------------------------


class TestCreateNugget:
    """Tests for POST /api/knowledge/nuggets."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/knowledge/nuggets",
                json={"group_id": str(GROUP_ID), "title": "T", "content": "C", "tags": []},
            )
        assert resp.status_code == 401

    async def test_creates_nugget_returns_201(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget()

        with patch("app.api.knowledge.create_manual_nugget", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(
                    "/api/knowledge/nuggets",
                    json={
                        "group_id": str(GROUP_ID),
                        "title": "My Note",
                        "content": "Some content",
                        "tags": ["tag1"],
                    },
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Nugget"

    async def test_validates_required_fields(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.post(
                "/api/knowledge/nuggets",
                json={"group_id": str(GROUP_ID)},
            )
        assert resp.status_code == 422

    async def test_commits_session(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget()

        with patch("app.api.knowledge.create_manual_nugget", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                await client.post(
                    "/api/knowledge/nuggets",
                    json={
                        "group_id": str(GROUP_ID),
                        "title": "Note",
                        "content": "Content",
                        "tags": [],
                    },
                )

        assert mock_session.commit.called


# ---------------------------------------------------------------------------
# POST /api/knowledge/nuggets/{nugget_id}/accept
# ---------------------------------------------------------------------------


class TestAcceptNugget:
    """Tests for POST /api/knowledge/nuggets/{nugget_id}/accept."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/accept")
        assert resp.status_code == 401

    async def test_returns_200_on_accept(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.accepted)

        with patch("app.api.knowledge.accept_suggestion", new_callable=AsyncMock) as mock_accept:
            mock_accept.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/accept")

        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    async def test_returns_404_when_not_found(self) -> None:
        mock_session = _make_mock_session()
        with patch("app.api.knowledge.accept_suggestion", new_callable=AsyncMock) as mock_accept:
            mock_accept.return_value = None
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/accept")

        assert resp.status_code == 404

    async def test_commits_session(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.accepted)

        with patch("app.api.knowledge.accept_suggestion", new_callable=AsyncMock) as mock_accept:
            mock_accept.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/accept")

        assert mock_session.commit.called


# ---------------------------------------------------------------------------
# POST /api/knowledge/nuggets/{nugget_id}/reject
# ---------------------------------------------------------------------------


class TestRejectNugget:
    """Tests for POST /api/knowledge/nuggets/{nugget_id}/reject."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/reject")
        assert resp.status_code == 401

    async def test_returns_200_on_reject(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.rejected)

        with patch("app.api.knowledge.reject_suggestion", new_callable=AsyncMock) as mock_reject:
            mock_reject.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/reject")

        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_returns_404_when_not_found(self) -> None:
        mock_session = _make_mock_session()
        with patch("app.api.knowledge.reject_suggestion", new_callable=AsyncMock) as mock_reject:
            mock_reject.return_value = None
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/reject")

        assert resp.status_code == 404

    async def test_commits_session(self) -> None:
        mock_session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.rejected)

        with patch("app.api.knowledge.reject_suggestion", new_callable=AsyncMock) as mock_reject:
            mock_reject.return_value = mock_nugget
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                await client.post(f"/api/knowledge/nuggets/{NUGGET_ID}/reject")

        assert mock_session.commit.called


# ---------------------------------------------------------------------------
# POST /api/knowledge/threads/{thread_id}/extract — LLM extraction
# ---------------------------------------------------------------------------


class TestExtractFromThread:
    """Tests for POST /api/knowledge/threads/{thread_id}/extract."""

    async def test_unauthenticated_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/knowledge/threads/{THREAD_ID}/extract")
        assert resp.status_code == 401

    async def test_returns_403_without_llm_consent(self) -> None:
        mock_session = _make_mock_session()
        # The consent check requires querying the user
        mock_user = _make_mock_user(llm_consent_given_at=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", _make_auth_cookie())
            resp = await client.post(f"/api/knowledge/threads/{THREAD_ID}/extract")

        assert resp.status_code == 403

    async def test_returns_200_with_consent(self) -> None:
        mock_session = _make_mock_session()
        now = datetime.now(tz=UTC)
        mock_user = _make_mock_user(llm_consent_given_at=now)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_nugget = _make_mock_nugget(
            status=NuggetStatus.suggested,
            source_type=NuggetSourceType.llm_extracted,
        )

        with patch(
            "app.api.knowledge.process_thread_for_nuggets", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = [mock_nugget]
            # First execute call is for consent check, subsequent for the endpoint logic
            mock_session.execute.return_value = mock_result
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/threads/{THREAD_ID}/extract")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nuggets"]) == 1

    async def test_returns_400_for_thread_size_violation(self) -> None:
        mock_session = _make_mock_session()
        now = datetime.now(tz=UTC)
        mock_user = _make_mock_user(llm_consent_given_at=now)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        with patch(
            "app.api.knowledge.process_thread_for_nuggets", new_callable=AsyncMock
        ) as mock_process:
            mock_process.side_effect = ValueError("Thread must have between 2 and 20 messages")
            mock_session.execute.return_value = mock_result
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                resp = await client.post(f"/api/knowledge/threads/{THREAD_ID}/extract")

        assert resp.status_code == 400

    async def test_commits_session_on_success(self) -> None:
        mock_session = _make_mock_session()
        now = datetime.now(tz=UTC)
        mock_user = _make_mock_user(llm_consent_given_at=now)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        with patch(
            "app.api.knowledge.process_thread_for_nuggets", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = []
            mock_session.execute.return_value = mock_result
            app = _make_test_app(session_override=mock_session)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("access_token", _make_auth_cookie())
                await client.post(f"/api/knowledge/threads/{THREAD_ID}/extract")

        assert mock_session.commit.called
