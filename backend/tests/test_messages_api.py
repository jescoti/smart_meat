"""Tests for the Messages API endpoints (thread listing and thread detail).

TDD RED phase — tests written before implementation.
Tests thread list pagination, sorting, ownership, thread detail with hierarchy,
ghost messages, and auth requirements.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
OTHER_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440099")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
THREAD_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
MESSAGE_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")
MESSAGE_ID_3 = uuid.UUID("880e8400-e29b-41d4-a716-446655440003")


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with the messages router for testing."""
    from fastapi import FastAPI

    from app.api.messages import _get_session_dependency, create_messages_router

    app = FastAPI()
    router = create_messages_router()
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


def _make_mock_thread(
    *,
    thread_id: uuid.UUID = THREAD_ID,
    group_id: uuid.UUID = GROUP_ID,
    subject: str = "Test Thread Subject",
    message_count: int = 5,
    participant_count: int = 3,
    last_message_at: datetime | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Thread ORM object."""
    thread = MagicMock()
    thread.id = thread_id
    thread.group_id = group_id
    thread.subject = subject
    thread.message_count = message_count
    thread.participant_count = participant_count
    thread.last_message_at = last_message_at or datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
    thread.created_at = created_at or datetime(2024, 1, 10, 8, 0, tzinfo=UTC)
    return thread


def _make_mock_group(
    *,
    group_id: uuid.UUID = GROUP_ID,
    owner_id: uuid.UUID = USER_ID,
) -> MagicMock:
    """Create a mock Group ORM object."""
    group = MagicMock()
    group.id = group_id
    group.owner_id = owner_id
    return group


def _make_mock_thread_message(
    *,
    tm_id: uuid.UUID | None = None,
    thread_id: uuid.UUID = THREAD_ID,
    message_id: uuid.UUID = MESSAGE_ID_1,
    parent_message_id: uuid.UUID | None = None,
    depth: int = 0,
    position: int = 0,
    is_ghost: bool = False,
) -> MagicMock:
    """Create a mock ThreadMessage ORM object."""
    tm = MagicMock()
    tm.id = tm_id or uuid.uuid4()
    tm.thread_id = thread_id
    tm.message_id = message_id
    tm.parent_message_id = parent_message_id
    tm.depth = depth
    tm.position = position
    tm.is_ghost = is_ghost
    return tm


def _make_mock_message(
    *,
    msg_id: uuid.UUID = MESSAGE_ID_1,
    group_id: uuid.UUID = GROUP_ID,
    sender_email: str = "alice@example.com",
    sender_name: str | None = "Alice",
    subject: str = "Test Subject",
    body_text: str | None = "Hello, this is the message body.",
    body_html: str | None = None,
    gmail_date: datetime | None = None,
) -> MagicMock:
    """Create a mock Message ORM object."""
    msg = MagicMock()
    msg.id = msg_id
    msg.group_id = group_id
    msg.sender_email = sender_email
    msg.sender_name = sender_name
    msg.subject = subject
    msg.body_text = body_text
    msg.body_html = body_html
    msg.date = gmail_date or datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
    return msg


class TestGetUserIdFromState:
    """Tests for _get_user_id when request.state.user_id is set (auth middleware path)."""

    async def test_user_id_from_request_state(self) -> None:
        """When auth middleware sets request.state.user_id, it should be used."""
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        from fastapi import FastAPI

        from app.api.messages import _get_session_dependency, create_messages_router

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
                request.state.user_id = str(USER_ID)
                return await call_next(request)

        mock_session = _make_mock_session()

        # Group ownership check
        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        # Count
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        # Threads
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = FastAPI()
        router = create_messages_router()
        app.include_router(router)
        app.add_middleware(InjectUserMiddleware)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/groups/{GROUP_ID}/threads")

        assert resp.status_code == 200


class TestListThreads:
    """Tests for GET /api/groups/{group_id}/threads."""

    async def test_list_threads_returns_200(self) -> None:
        mock_session = _make_mock_session()
        # First execute: group ownership check
        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        # Second execute: count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        # Third execute: thread list query
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_list_threads_returns_correct_structure(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = [mock_thread]

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert "threads" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 20

    async def test_list_threads_returns_thread_data(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread(
            subject="Discussion about project",
            message_count=10,
            participant_count=4,
        )

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = [mock_thread]

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        thread = data["threads"][0]
        assert thread["id"] == str(THREAD_ID)
        assert thread["subject"] == "Discussion about project"
        assert thread["message_count"] == 10
        assert thread["participant_count"] == 4
        assert "last_message_at" in thread
        assert "created_at" in thread

    async def test_list_threads_pagination_custom_params(self) -> None:
        mock_session = _make_mock_session()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads?page=3&per_page=10",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["page"] == 3
        assert data["per_page"] == 10
        assert data["total"] == 50

    async def test_list_threads_empty_results(self) -> None:
        mock_session = _make_mock_session()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["threads"] == []
        assert data["total"] == 0

    async def test_list_threads_group_not_owned_returns_404(self) -> None:
        mock_session = _make_mock_session()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_group_result)

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_list_threads_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/groups/{GROUP_ID}/threads")

        assert resp.status_code == 401

    async def test_list_threads_with_sort_param(self) -> None:
        """Verify that the sort parameter is accepted."""
        mock_session = _make_mock_session()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_threads_result = MagicMock()
        mock_threads_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_count_result, mock_threads_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/groups/{GROUP_ID}/threads?sort=created_at_desc",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200


class TestGetThreadDetail:
    """Tests for GET /api/threads/{thread_id}."""

    async def test_thread_detail_returns_200(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        # First execute: thread lookup with group ownership check
        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        # Second execute: group ownership
        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        # Third execute: thread messages with joined messages
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message()
        mock_tm.message = mock_msg

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = [mock_tm]

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 200

    async def test_thread_detail_returns_thread_info(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread(subject="Important Discussion")

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert data["thread"]["id"] == str(THREAD_ID)
        assert data["thread"]["subject"] == "Important Discussion"

    async def test_thread_detail_returns_messages(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        mock_msg = _make_mock_message(
            sender_email="alice@example.com",
            sender_name="Alice",
            subject="Test Subject",
            body_text="Hello world",
            body_html="<p>Hello world</p>",
            gmail_date=datetime(2024, 1, 12, 9, 0, tzinfo=UTC),
        )
        mock_tm = _make_mock_thread_message(
            message_id=MESSAGE_ID_1,
            depth=0,
            position=0,
            is_ghost=False,
        )
        mock_tm.message = mock_msg

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = [mock_tm]

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        messages = data["messages"]
        assert len(messages) == 1
        msg = messages[0]
        assert msg["id"] == str(MESSAGE_ID_1)
        assert msg["sender_email"] == "alice@example.com"
        assert msg["sender_name"] == "Alice"
        assert msg["subject"] == "Test Subject"
        assert msg["body_text"] == "Hello world"
        assert msg["body_html"] == "<p>Hello world</p>"
        assert msg["depth"] == 0
        assert msg["is_ghost"] is False
        assert msg["parent_message_id"] is None

    async def test_thread_detail_includes_ghost_messages(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        # Ghost message — is_ghost=True, message will have minimal info
        mock_ghost_msg = _make_mock_message(
            msg_id=MESSAGE_ID_2,
            sender_email="",
            sender_name=None,
            subject="",
            body_text=None,
            body_html=None,
        )
        mock_ghost_tm = _make_mock_thread_message(
            message_id=MESSAGE_ID_2,
            depth=0,
            position=0,
            is_ghost=True,
        )
        mock_ghost_tm.message = mock_ghost_msg

        # Real message as child
        mock_real_msg = _make_mock_message(
            msg_id=MESSAGE_ID_3,
            sender_email="bob@example.com",
            sender_name="Bob",
        )
        mock_real_tm = _make_mock_thread_message(
            message_id=MESSAGE_ID_3,
            parent_message_id=MESSAGE_ID_2,
            depth=1,
            position=1,
            is_ghost=False,
        )
        mock_real_tm.message = mock_real_msg

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = [mock_ghost_tm, mock_real_tm]

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        messages = data["messages"]
        assert len(messages) == 2
        assert messages[0]["is_ghost"] is True
        assert messages[1]["is_ghost"] is False
        assert messages[1]["parent_message_id"] == str(MESSAGE_ID_2)

    async def test_thread_detail_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_thread_result)

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_thread_detail_group_not_owned_returns_404(self) -> None:
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        # Group not owned by the user
        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_thread_detail_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/threads/{THREAD_ID}")

        assert resp.status_code == 401

    async def test_thread_detail_message_ordering(self) -> None:
        """Messages should be ordered by position (depth then date)."""
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        # Create 3 messages at different depths
        msg1 = _make_mock_message(msg_id=MESSAGE_ID_1, sender_email="alice@example.com")
        tm1 = _make_mock_thread_message(message_id=MESSAGE_ID_1, depth=0, position=0)
        tm1.message = msg1

        msg2 = _make_mock_message(msg_id=MESSAGE_ID_2, sender_email="bob@example.com")
        tm2 = _make_mock_thread_message(
            message_id=MESSAGE_ID_2,
            parent_message_id=MESSAGE_ID_1,
            depth=1,
            position=1,
        )
        tm2.message = msg2

        msg3 = _make_mock_message(msg_id=MESSAGE_ID_3, sender_email="charlie@example.com")
        tm3 = _make_mock_thread_message(
            message_id=MESSAGE_ID_3,
            parent_message_id=MESSAGE_ID_1,
            depth=1,
            position=2,
        )
        tm3.message = msg3

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = [tm1, tm2, tm3]

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        messages = data["messages"]
        assert len(messages) == 3
        # First message is root (depth 0)
        assert messages[0]["depth"] == 0
        # Second and third are children (depth 1)
        assert messages[1]["depth"] == 1
        assert messages[2]["depth"] == 1

    async def test_thread_detail_gmail_date_field(self) -> None:
        """Verify gmail_date field is included in message response."""
        mock_session = _make_mock_session()
        mock_thread = _make_mock_thread()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = mock_thread

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        dt = datetime(2024, 3, 15, 14, 30, tzinfo=UTC)
        mock_msg = _make_mock_message(msg_id=MESSAGE_ID_1, gmail_date=dt)
        mock_tm = _make_mock_thread_message(message_id=MESSAGE_ID_1)
        mock_tm.message = mock_msg

        mock_tms_result = MagicMock()
        mock_tms_result.scalars.return_value.all.return_value = [mock_tm]

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_group_result, mock_tms_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/threads/{THREAD_ID}",
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        msg = data["messages"][0]
        assert "gmail_date" in msg
        assert msg["gmail_date"] == dt.isoformat()
