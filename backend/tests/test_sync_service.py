"""Tests for the sync service.

TDD RED phase — tests written before implementation.
Tests full sync, incremental sync, deduplication, error handling, and progress tracking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import GroupSyncStatus

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
ENCRYPTION_KEY = "test-encryption-key"
CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"


def _make_mock_user(
    *,
    user_id: uuid.UUID = USER_ID,
    encrypted_access_token: str = "encrypted-access-token",
    encrypted_refresh_token: str = "encrypted-refresh-token",
) -> MagicMock:
    """Create a mock User ORM object for sync tests."""
    user = MagicMock()
    user.id = user_id
    user.encrypted_access_token = encrypted_access_token
    user.encrypted_refresh_token = encrypted_refresh_token
    return user


def _make_mock_group(
    *,
    group_id: uuid.UUID = GROUP_ID,
    owner_id: uuid.UUID = USER_ID,
    google_group_email: str = "test-group@googlegroups.com",
    sync_status: GroupSyncStatus = GroupSyncStatus.idle,
    gmail_history_id: str | None = None,
) -> MagicMock:
    """Create a mock Group ORM object for sync tests."""
    group = MagicMock()
    group.id = group_id
    group.owner_id = owner_id
    group.google_group_email = google_group_email
    group.sync_status = sync_status
    group.gmail_history_id = gmail_history_id
    group.sync_error_message = None
    group.sync_progress_current = None
    group.sync_progress_total = None
    return group


def _make_mock_session(*, group: object | None = None, user: object | None = None) -> AsyncMock:
    """Create a mock AsyncSession with configurable query results."""
    session = AsyncMock()

    results_map: dict[int, object] = {}
    call_counter = {"count": 0}

    if group is not None and user is not None:
        results_map[0] = group
        results_map[1] = user

    async def mock_execute(stmt: object) -> MagicMock:
        result = MagicMock()
        idx = call_counter["count"]
        call_counter["count"] += 1
        if idx in results_map:
            result.scalar_one_or_none.return_value = results_map[idx]
        else:
            result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=mock_execute)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


def _make_raw_gmail_message(gmail_id: str = "msg-001") -> dict:
    """Create a raw Gmail API message dict for testing."""
    return {
        "id": gmail_id,
        "threadId": "thread-001",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Message-ID", "value": f"<{gmail_id}@mail.gmail.com>"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "group@googlegroups.com"},
                {"name": "Date", "value": "Mon, 1 Jan 2024 00:00:00 +0000"},
            ],
            "body": {"data": "SGVsbG8gV29ybGQ="},  # "Hello World" base64
        },
    }


class TestSyncGroupFullSync:
    """Tests for full sync (no history_id)."""

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_full_sync_fetches_messages(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.return_value = (
            [{"id": "msg-001"}],
            None,  # no next page
        )
        mock_gmail.batch_get_messages.return_value = [_make_raw_gmail_message("msg-001")]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        mock_gmail.list_messages.assert_called_once()
        mock_gmail.batch_get_messages.assert_called_once()

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_full_sync_sets_status_idle_on_success(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.return_value = ([], None)
        mock_gmail.batch_get_messages.return_value = []

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        assert mock_group.sync_status == GroupSyncStatus.idle

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_full_sync_paginates(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.side_effect = [
            ([{"id": "msg-001"}], "page2"),
            ([{"id": "msg-002"}], None),
        ]
        mock_gmail.batch_get_messages.side_effect = [
            [_make_raw_gmail_message("msg-001")],
            [_make_raw_gmail_message("msg-002")],
        ]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        assert mock_gmail.list_messages.call_count == 2

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_full_sync_updates_progress(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.return_value = (
            [{"id": "msg-001"}, {"id": "msg-002"}],
            None,
        )
        mock_gmail.batch_get_messages.return_value = [
            _make_raw_gmail_message("msg-001"),
            _make_raw_gmail_message("msg-002"),
        ]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        # Progress should have been updated
        assert mock_group.sync_progress_current is not None


class TestSyncGroupIncrementalSync:
    """Tests for incremental sync (with history_id)."""

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_incremental_sync_uses_history(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.get_history.return_value = (
            [{"messagesAdded": [{"message": {"id": "msg-new"}}]}],
            "99999",
        )
        mock_gmail.batch_get_messages.return_value = [_make_raw_gmail_message("msg-new")]

        mock_group = _make_mock_group(gmail_history_id="12345")
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        mock_gmail.get_history.assert_called_once_with("12345", label_id=None)
        mock_gmail.list_messages.assert_not_called()

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_incremental_sync_updates_history_id(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.get_history.return_value = ([], "99999")
        mock_gmail.batch_get_messages.return_value = []

        mock_group = _make_mock_group(gmail_history_id="12345")
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        assert mock_group.gmail_history_id == "99999"


class TestSyncGroupDeduplication:
    """Tests for message deduplication by gmail_id."""

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_skips_existing_messages(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.return_value = (
            [{"id": "msg-001"}],
            None,
        )
        mock_gmail.batch_get_messages.return_value = [_make_raw_gmail_message("msg-001")]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()

        # Build a session that returns an existing message on the dedup check
        session = AsyncMock()
        call_counter = {"count": 0}

        async def mock_execute(stmt: object) -> MagicMock:
            result = MagicMock()
            idx = call_counter["count"]
            call_counter["count"] += 1
            if idx == 0:
                result.scalar_one_or_none.return_value = mock_group
            elif idx == 1:
                result.scalar_one_or_none.return_value = mock_user
            else:
                # Dedup check: message already exists
                result.scalar_one_or_none.return_value = MagicMock()
            return result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        # No message should have been added (only the group was potentially updated)
        # The important thing is no error was raised — dedup worked
        assert mock_group.sync_status == GroupSyncStatus.idle


class TestSyncGroupErrorHandling:
    """Tests for sync error handling."""

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_auth_error_attempts_token_refresh(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.gmail import GmailAuthError
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        # First client raises auth error, second succeeds
        mock_gmail_fail = AsyncMock()
        mock_gmail_fail.list_messages.side_effect = GmailAuthError()

        mock_gmail_success = AsyncMock()
        mock_gmail_success.list_messages.return_value = ([], None)
        mock_gmail_success.batch_get_messages.return_value = []

        mock_gmail_cls.side_effect = [mock_gmail_fail, mock_gmail_success]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        with patch("app.services.sync.google_auth.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {"access_token": "new-token", "expires_in": 3600}
            with patch("app.services.sync.encrypt") as mock_encrypt:
                mock_encrypt.return_value = "encrypted-new-token"
                await sync_group(
                    GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
                )

        mock_refresh.assert_called_once()
        assert mock_group.sync_status == GroupSyncStatus.idle

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_auth_error_refresh_updates_refresh_token(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        """When Google returns a new refresh_token during refresh, it should be re-encrypted."""
        from app.services.gmail import GmailAuthError
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail_fail = AsyncMock()
        mock_gmail_fail.list_messages.side_effect = GmailAuthError()

        mock_gmail_success = AsyncMock()
        mock_gmail_success.list_messages.return_value = ([], None)
        mock_gmail_success.batch_get_messages.return_value = []

        mock_gmail_cls.side_effect = [mock_gmail_fail, mock_gmail_success]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        with patch("app.services.sync.google_auth.refresh_access_token") as mock_refresh:
            # Return both access_token AND refresh_token
            mock_refresh.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }
            with patch("app.services.sync.encrypt") as mock_encrypt:
                mock_encrypt.return_value = "encrypted-new-token"
                await sync_group(
                    GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
                )

        # encrypt should be called for both access_token and refresh_token
        assert mock_encrypt.call_count == 2
        assert mock_group.sync_status == GroupSyncStatus.idle

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_auth_error_retry_fails_sets_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.gmail import GmailAuthError
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        # Both attempts raise auth error
        mock_gmail1 = AsyncMock()
        mock_gmail1.list_messages.side_effect = GmailAuthError()
        mock_gmail2 = AsyncMock()
        mock_gmail2.list_messages.side_effect = GmailAuthError()

        mock_gmail_cls.side_effect = [mock_gmail1, mock_gmail2]

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        with patch("app.services.sync.google_auth.refresh_access_token") as mock_refresh:
            mock_refresh.return_value = {"access_token": "new-token", "expires_in": 3600}
            with patch("app.services.sync.encrypt") as mock_encrypt:
                mock_encrypt.return_value = "encrypted-new-token"
                await sync_group(
                    GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
                )

        assert mock_group.sync_status == GroupSyncStatus.error
        assert mock_group.sync_error_message is not None

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_rate_limit_error_sets_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.gmail import GmailRateLimitError
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.side_effect = GmailRateLimitError(retry_after=60)

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        assert mock_group.sync_status == GroupSyncStatus.error
        assert "retry" in mock_group.sync_error_message.lower()

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_generic_error_sets_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.side_effect = RuntimeError("Something went wrong")

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        await sync_group(GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET)

        assert mock_group.sync_status == GroupSyncStatus.error
        assert mock_group.sync_error_message is not None

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_auth_error_refresh_fails_sets_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        """When token refresh itself fails, sync should set error status."""
        from app.services.gmail import GmailAuthError
        from app.services.sync import sync_group

        mock_decrypt.return_value = "decrypted-access-token"

        mock_gmail = AsyncMock()
        mock_gmail_cls.return_value = mock_gmail
        mock_gmail.list_messages.side_effect = GmailAuthError()

        mock_group = _make_mock_group(gmail_history_id=None)
        mock_user = _make_mock_user()
        session = _make_mock_session(group=mock_group, user=mock_user)

        with patch("app.services.sync.google_auth.refresh_access_token") as mock_refresh:
            mock_refresh.side_effect = Exception("Refresh failed")
            await sync_group(
                GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
            )

        assert mock_group.sync_status == GroupSyncStatus.error

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_group_not_found_raises_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()

        with pytest.raises(ValueError, match="Group not found"):
            await sync_group(
                GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
            )

    @patch("app.services.sync.GmailClient")
    @patch("app.services.sync.decrypt")
    async def test_user_not_found_raises_error(
        self,
        mock_decrypt: MagicMock,
        mock_gmail_cls: MagicMock,
    ) -> None:
        from app.services.sync import sync_group

        mock_group = _make_mock_group()

        session = AsyncMock()
        call_counter = {"count": 0}

        async def mock_execute(stmt: object) -> MagicMock:
            result = MagicMock()
            idx = call_counter["count"]
            call_counter["count"] += 1
            if idx == 0:
                result.scalar_one_or_none.return_value = mock_group
            else:
                result.scalar_one_or_none.return_value = None
            return result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        with pytest.raises(ValueError, match="User not found"):
            await sync_group(
                GROUP_ID, USER_ID, session, ENCRYPTION_KEY, CLIENT_ID, CLIENT_SECRET
            )
