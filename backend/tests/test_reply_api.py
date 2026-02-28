"""Tests for the Reply API endpoint — POST /api/threads/{thread_id}/reply.

TDD RED phase — tests written before implementation.
Tests successful reply, authorization, RFC 5322 header construction, audit log,
thread counter updates, and error handling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
OTHER_USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440099")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
THREAD_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
MESSAGE_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")

PARENT_MSG_ID_HEADER = "<original-msg-id@mail.example.com>"
GROUP_EMAIL = "test-group@googlegroups.com"
USER_EMAIL = "user@example.com"
ENCRYPTION_KEY = "test-encryption-key-for-unit-tests"


def _make_test_app(*, session_override: object | None = None) -> object:
    """Create a minimal FastAPI app with the reply router for testing."""
    from fastapi import FastAPI

    from app.api.reply import _get_session_dependency, create_reply_router

    app = FastAPI()
    router = create_reply_router()
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


def _make_mock_message(
    *,
    msg_id: uuid.UUID = MESSAGE_ID_1,
    group_id: uuid.UUID = GROUP_ID,
    message_id_header: str = PARENT_MSG_ID_HEADER,
    references_header: list[str] | None = None,
    subject: str = "Test Thread Subject",
    sender_email: str = "alice@example.com",
    sender_name: str | None = "Alice",
    body_text: str | None = "Original message body.",
    date: datetime | None = None,
) -> MagicMock:
    """Create a mock Message ORM object."""
    msg = MagicMock()
    msg.id = msg_id
    msg.group_id = group_id
    msg.message_id_header = message_id_header
    msg.references_header = references_header
    msg.subject = subject
    msg.sender_email = sender_email
    msg.sender_name = sender_name
    msg.body_text = body_text
    msg.date = date or datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
    return msg


def _make_mock_thread(
    *,
    thread_id: uuid.UUID = THREAD_ID,
    group_id: uuid.UUID = GROUP_ID,
    subject: str = "Test Thread Subject",
    message_count: int = 5,
    participant_count: int = 3,
) -> MagicMock:
    """Create a mock Thread ORM object."""
    thread = MagicMock()
    thread.id = thread_id
    thread.group_id = group_id
    thread.subject = subject
    thread.message_count = message_count
    thread.participant_count = participant_count
    return thread


def _make_mock_group(
    *,
    group_id: uuid.UUID = GROUP_ID,
    owner_id: uuid.UUID = USER_ID,
    google_group_email: str = GROUP_EMAIL,
) -> MagicMock:
    """Create a mock Group ORM object."""
    group = MagicMock()
    group.id = group_id
    group.owner_id = owner_id
    group.google_group_email = google_group_email
    return group


def _make_mock_user(
    *,
    user_id: uuid.UUID = USER_ID,
    email: str = USER_EMAIL,
    encrypted_access_token: str = "encrypted-token",
) -> MagicMock:
    """Create a mock User ORM object."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.encrypted_access_token = encrypted_access_token
    return user


def _setup_successful_reply_mocks(mock_session: AsyncMock) -> dict:
    """Set up mock session to simulate a successful reply flow.

    Returns a dict of the mock objects for further assertions.
    """
    mock_parent_msg = _make_mock_message()
    mock_thread = _make_mock_thread()
    mock_group = _make_mock_group()
    mock_user = _make_mock_user()

    # Query 1: Load parent message
    mock_msg_result = MagicMock()
    mock_msg_result.scalar_one_or_none.return_value = mock_parent_msg

    # Query 2: Load thread
    mock_thread_result = MagicMock()
    mock_thread_result.scalar_one_or_none.return_value = mock_thread

    # Query 3: Load group (ownership verification)
    mock_group_result = MagicMock()
    mock_group_result.scalar_one_or_none.return_value = mock_group

    # Query 4: Load user (for email and access token)
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    # Query 5: Count distinct senders for participant_count update
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 4

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_msg_result,
            mock_thread_result,
            mock_group_result,
            mock_user_result,
            mock_count_result,
        ]
    )

    return {
        "parent_msg": mock_parent_msg,
        "thread": mock_thread,
        "group": mock_group,
        "user": mock_user,
    }


class TestReplyEndpointSuccess:
    """Tests for successful reply flow."""

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_successful_reply_returns_201(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        # Mock GmailClient.send_message
        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {
            "id": "gmail-sent-id",
            "threadId": "gmail-thread-id",
        }
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "This is my reply.",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 201

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_successful_reply_returns_message_data(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {
            "id": "gmail-sent-id",
            "threadId": "gmail-thread-id",
        }
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "This is my reply.",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        data = resp.json()
        assert "message" in data
        assert "id" in data["message"]
        assert data["message"]["body_text"] == "This is my reply."
        assert data["message"]["sender_email"] == USER_EMAIL

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_stores_message_locally(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {
            "id": "gmail-sent-id",
            "threadId": "gmail-thread-id",
        }
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "This is my reply.",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        # session.add should be called at least twice: Message + ThreadMessage + AuditLog
        assert mock_session.add.call_count >= 3
        assert mock_session.commit.called

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_creates_audit_log(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {
            "id": "gmail-sent-id",
            "threadId": "gmail-thread-id",
        }
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "My reply.",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        # Find the AuditLog among the session.add calls
        added_objects = [call.args[0] for call in mock_session.add.call_args_list]
        from app.db.models import AuditLog

        audit_logs = [obj for obj in added_objects if isinstance(obj, AuditLog)]
        assert len(audit_logs) == 1
        assert audit_logs[0].action == "reply_send"
        assert audit_logs[0].resource_type == "thread"
        assert audit_logs[0].resource_id == str(THREAD_ID)

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_sends_via_gmail_client(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {
            "id": "gmail-sent-id",
            "threadId": "gmail-thread-id",
        }
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "My reply.",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        # GmailClient should be instantiated with the decrypted access token
        mock_gmail_cls.assert_called_once_with("decrypted-access-token")
        mock_gmail_instance.send_message.assert_called_once()


class TestReplyRfc5322Headers:
    """Tests for correct RFC 5322 header construction."""

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_in_reply_to_set_to_parent_message_id(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        # Check the raw message sent to Gmail
        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        assert f"In-Reply-To: {PARENT_MSG_ID_HEADER}" in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_references_includes_parent_chain(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        mocks = _setup_successful_reply_mocks(mock_session)
        # Set parent's references to include prior messages
        mocks["parent_msg"].references_header = ["<ref1@mail.com>", "<ref2@mail.com>"]

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        # References should include parent's references + parent's own message_id_header
        assert "<ref1@mail.com>" in raw_message
        assert "<ref2@mail.com>" in raw_message
        assert PARENT_MSG_ID_HEADER in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_subject_has_re_prefix(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        assert "Subject: Re: Test Thread Subject" in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_subject_does_not_double_re_prefix(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        mocks = _setup_successful_reply_mocks(mock_session)
        mocks["thread"].subject = "Re: Already prefixed"

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        assert "Subject: Re: Already prefixed" in raw_message
        assert "Subject: Re: Re:" not in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_message_id_format(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        # Message-ID should be in format <uuid@smartmeat.app>
        assert "Message-ID: <" in raw_message
        assert "@smartmeat.app>" in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_to_header_is_group_email(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        assert f"To: {GROUP_EMAIL}" in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_from_header_is_user_email(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        assert f"From: {USER_EMAIL}" in raw_message

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_references_empty_when_parent_has_none(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        mocks = _setup_successful_reply_mocks(mock_session)
        mocks["parent_msg"].references_header = None

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        raw_message = mock_gmail_instance.send_message.call_args[0][0]
        # References should contain just the parent's message_id_header
        assert f"References: {PARENT_MSG_ID_HEADER}" in raw_message


class TestReplyErrorCases:
    """Tests for reply error handling."""

    async def test_missing_user_id_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
            )

        assert resp.status_code == 401

    async def test_parent_message_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_msg_result)

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_thread_not_found_returns_404(self) -> None:
        mock_session = _make_mock_session()

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = _make_mock_message()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[mock_msg_result, mock_thread_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 404

    async def test_group_not_owned_returns_403(self) -> None:
        mock_session = _make_mock_session()

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = _make_mock_message()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = _make_mock_thread()

        # Group not owned by current user
        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[mock_msg_result, mock_thread_result, mock_group_result]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 403

    async def test_empty_body_text_returns_422(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 422

    async def test_missing_body_text_returns_422(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 422

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_gmail_send_failure_returns_502(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        from app.services.gmail import GmailAPIError

        mock_gmail_instance.send_message.side_effect = GmailAPIError(
            status_code=500, message="Gmail error"
        )
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 502


class TestReplyThreadUpdates:
    """Tests for thread counter updates after reply."""

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_increments_message_count(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        mock_session = _make_mock_session()
        mocks = _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        # Thread message_count should be incremented
        assert mocks["thread"].message_count == 6  # was 5, now 6


class TestReplyUserIdFromRequestState:
    """Tests for _get_user_id when request.state.user_id is set (auth middleware)."""

    @patch("app.api.reply.decrypt", return_value="decrypted-access-token")
    @patch("app.api.reply.GmailClient")
    @patch("app.api.reply.ENCRYPTION_KEY", ENCRYPTION_KEY)
    async def test_user_id_from_request_state(
        self,
        mock_gmail_cls: MagicMock,
        mock_decrypt: MagicMock,
    ) -> None:
        """When auth middleware sets request.state.user_id, it should be used."""
        from fastapi import FastAPI
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        from app.api.reply import _get_session_dependency, create_reply_router

        class InjectUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self, request: Request, call_next: RequestResponseEndpoint
            ) -> Response:
                request.state.user_id = str(USER_ID)
                return await call_next(request)

        mock_session = _make_mock_session()
        _setup_successful_reply_mocks(mock_session)

        mock_gmail_instance = AsyncMock()
        mock_gmail_instance.send_message.return_value = {"id": "sent", "threadId": "t1"}
        mock_gmail_cls.return_value = mock_gmail_instance

        app = FastAPI()
        router = create_reply_router()
        app.include_router(router)
        app.add_middleware(InjectUserMiddleware)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply via auth middleware.",
                },
            )

        assert resp.status_code == 201


class TestReplyUserNotFound:
    """Test for user not found after ownership check passes."""

    async def test_user_not_found_returns_401(self) -> None:
        mock_session = _make_mock_session()

        mock_msg_result = MagicMock()
        mock_msg_result.scalar_one_or_none.return_value = _make_mock_message()

        mock_thread_result = MagicMock()
        mock_thread_result.scalar_one_or_none.return_value = _make_mock_thread()

        mock_group_result = MagicMock()
        mock_group_result.scalar_one_or_none.return_value = _make_mock_group()

        # User not found
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_msg_result,
                mock_thread_result,
                mock_group_result,
                mock_user_result,
            ]
        )

        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/threads/{THREAD_ID}/reply",
                json={
                    "parent_message_id": str(MESSAGE_ID_1),
                    "body_text": "Reply text",
                },
                headers={"X-User-Id": str(USER_ID)},
            )

        assert resp.status_code == 401
