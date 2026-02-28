"""Tests for the knowledge service — CRUD operations and LLM extraction.

TDD RED phase -- these tests are written before the implementation.
All database operations are mocked via AsyncMock sessions.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import Nugget, NuggetSourceType, NuggetStatus
from app.services.knowledge import (
    accept_suggestion,
    create_manual_nugget,
    get_nugget,
    list_nuggets,
    process_thread_for_nuggets,
    reject_suggestion,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440001")
NUGGET_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440002")
THREAD_ID = uuid.UUID("880e8400-e29b-41d4-a716-446655440003")
MESSAGE_ID = uuid.UUID("990e8400-e29b-41d4-a716-446655440004")
MODEL = "claude-sonnet-4-5-20250514"
API_KEY = "test-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _make_mock_nugget(
    *,
    nugget_id: uuid.UUID = NUGGET_ID,
    status: NuggetStatus = NuggetStatus.suggested,
    source_type: NuggetSourceType = NuggetSourceType.llm_extracted,
    created_by: uuid.UUID = USER_ID,
) -> MagicMock:
    """Create a mock Nugget ORM object."""
    nugget = MagicMock(spec=Nugget)
    nugget.id = nugget_id
    nugget.group_id = GROUP_ID
    nugget.source_message_id = None
    nugget.title = "Test Nugget"
    nugget.content = "Test content"
    nugget.tags = ["test"]
    nugget.source_type = source_type
    nugget.status = status
    nugget.created_by = created_by
    nugget.created_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    nugget.updated_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
    return nugget


def _make_mock_thread(*, message_count: int = 5) -> MagicMock:
    """Create a mock Thread ORM object."""
    thread = MagicMock()
    thread.id = THREAD_ID
    thread.group_id = GROUP_ID
    thread.subject = "Test Thread"
    thread.message_count = message_count
    return thread


def _make_mock_message(*, msg_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock Message ORM object."""
    msg = MagicMock()
    msg.id = msg_id or MESSAGE_ID
    msg.group_id = GROUP_ID
    msg.sender_name = "Alice"
    msg.body_text = "Hello, world!"
    msg.date = datetime(2024, 6, 10, 10, 0, 0, tzinfo=UTC)
    return msg


def _make_mock_thread_message(msg: MagicMock) -> MagicMock:
    """Create a mock ThreadMessage ORM object."""
    tm = MagicMock()
    tm.message = msg
    return tm


# ---------------------------------------------------------------------------
# create_manual_nugget tests
# ---------------------------------------------------------------------------


class TestCreateManualNugget:
    """Tests for create_manual_nugget."""

    async def test_creates_nugget_with_correct_fields(self) -> None:
        session = _make_mock_session()
        result = await create_manual_nugget(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            source_message_id=None,
            title="My Note",
            content="Some content",
            tags=["tag1"],
        )
        assert isinstance(result, Nugget)
        assert result.title == "My Note"
        assert result.content == "Some content"
        assert result.tags == ["tag1"]
        assert result.source_type == NuggetSourceType.manual
        assert result.status == NuggetStatus.accepted
        assert result.created_by == USER_ID
        assert result.group_id == GROUP_ID

    async def test_adds_nugget_to_session(self) -> None:
        session = _make_mock_session()
        await create_manual_nugget(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            source_message_id=None,
            title="My Note",
            content="Content",
            tags=[],
        )
        assert session.add.called

    async def test_flushes_session(self) -> None:
        session = _make_mock_session()
        await create_manual_nugget(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            source_message_id=None,
            title="My Note",
            content="Content",
            tags=[],
        )
        assert session.flush.called

    async def test_creates_audit_log(self) -> None:
        session = _make_mock_session()
        await create_manual_nugget(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            source_message_id=None,
            title="My Note",
            content="Content",
            tags=[],
        )
        # session.add should be called twice: once for nugget, once for audit log
        assert session.add.call_count == 2

    async def test_with_source_message_id(self) -> None:
        session = _make_mock_session()
        result = await create_manual_nugget(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            source_message_id=MESSAGE_ID,
            title="My Note",
            content="Content",
            tags=[],
        )
        assert result.source_message_id == MESSAGE_ID


# ---------------------------------------------------------------------------
# list_nuggets tests
# ---------------------------------------------------------------------------


class TestListNuggets:
    """Tests for list_nuggets."""

    async def test_returns_nuggets_and_total(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget()

        # First call returns the count
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        # Second call returns nuggets
        nuggets_result = MagicMock()
        nuggets_scalars = MagicMock()
        nuggets_scalars.all.return_value = [mock_nugget]
        nuggets_result.scalars.return_value = nuggets_scalars

        session.execute.side_effect = [count_result, nuggets_result]

        nuggets, total = await list_nuggets(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            status=None,
            page=1,
            per_page=20,
        )
        assert total == 1
        assert len(nuggets) == 1

    async def test_filters_by_status(self) -> None:
        session = _make_mock_session()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        nuggets_result = MagicMock()
        nuggets_scalars = MagicMock()
        nuggets_scalars.all.return_value = []
        nuggets_result.scalars.return_value = nuggets_scalars

        session.execute.side_effect = [count_result, nuggets_result]

        nuggets, total = await list_nuggets(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            status=NuggetStatus.accepted,
            page=1,
            per_page=20,
        )
        assert total == 0
        assert nuggets == []

    async def test_pagination(self) -> None:
        session = _make_mock_session()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 25
        nuggets_result = MagicMock()
        nuggets_scalars = MagicMock()
        nuggets_scalars.all.return_value = []
        nuggets_result.scalars.return_value = nuggets_scalars

        session.execute.side_effect = [count_result, nuggets_result]

        nuggets, total = await list_nuggets(
            session=session,
            user_id=USER_ID,
            group_id=GROUP_ID,
            status=None,
            page=2,
            per_page=10,
        )
        assert total == 25


# ---------------------------------------------------------------------------
# get_nugget tests
# ---------------------------------------------------------------------------


class TestGetNugget:
    """Tests for get_nugget."""

    async def test_returns_nugget_when_found(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        result = await get_nugget(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is mock_nugget

    async def test_returns_none_when_not_found(self) -> None:
        session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await get_nugget(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is None


# ---------------------------------------------------------------------------
# accept_suggestion tests
# ---------------------------------------------------------------------------


class TestAcceptSuggestion:
    """Tests for accept_suggestion."""

    async def test_sets_status_to_accepted(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        result = await accept_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is not None
        assert result.status == NuggetStatus.accepted

    async def test_returns_none_when_not_found(self) -> None:
        session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await accept_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is None

    async def test_creates_audit_log(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        await accept_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert session.add.called

    async def test_flushes_session(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        await accept_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert session.flush.called


# ---------------------------------------------------------------------------
# reject_suggestion tests
# ---------------------------------------------------------------------------


class TestRejectSuggestion:
    """Tests for reject_suggestion."""

    async def test_sets_status_to_rejected(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        result = await reject_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is not None
        assert result.status == NuggetStatus.rejected

    async def test_returns_none_when_not_found(self) -> None:
        session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await reject_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert result is None

    async def test_creates_audit_log(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        await reject_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert session.add.called

    async def test_flushes_session(self) -> None:
        session = _make_mock_session()
        mock_nugget = _make_mock_nugget(status=NuggetStatus.suggested)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_nugget
        session.execute.return_value = mock_result

        await reject_suggestion(session=session, user_id=USER_ID, nugget_id=NUGGET_ID)
        assert session.flush.called


# ---------------------------------------------------------------------------
# process_thread_for_nuggets tests
# ---------------------------------------------------------------------------


class TestProcessThreadForNuggets:
    """Tests for process_thread_for_nuggets."""

    async def test_returns_list_of_nuggets(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=5)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        # First execute: get thread
        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread

        # Second execute: get thread messages
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        extracted = [
            {"title": "Nugget 1", "content": "Content 1", "tags": ["tag1"]},
        ]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = extracted
            result = await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

        assert len(result) == 1
        assert isinstance(result[0], Nugget)
        assert result[0].title == "Nugget 1"

    async def test_rejects_thread_with_fewer_than_2_messages(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=1)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        session.execute.return_value = thread_result

        with pytest.raises(ValueError, match="between 2 and 20"):
            await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

    async def test_rejects_thread_with_more_than_20_messages(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=25)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        session.execute.return_value = thread_result

        with pytest.raises(ValueError, match="between 2 and 20"):
            await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

    async def test_raises_when_thread_not_found(self) -> None:
        session = _make_mock_session()
        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = None
        session.execute.return_value = thread_result

        with pytest.raises(ValueError, match="not found"):
            await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

    async def test_creates_nuggets_with_suggested_status(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=3)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        extracted = [{"title": "T", "content": "C", "tags": []}]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = extracted
            result = await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

        assert result[0].status == NuggetStatus.suggested
        assert result[0].source_type == NuggetSourceType.llm_extracted

    async def test_creates_audit_log_entries(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=3)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        extracted = [{"title": "T", "content": "C", "tags": []}]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = extracted
            await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

        # Should have added nuggets + audit log entries
        assert session.add.call_count >= 2

    async def test_thread_at_boundary_2_messages(self) -> None:
        """Thread with exactly 2 messages should be processed."""
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=2)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = []
            result = await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )
        assert result == []

    async def test_thread_at_boundary_20_messages(self) -> None:
        """Thread with exactly 20 messages should be processed."""
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=20)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = []
            result = await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )
        assert result == []

    async def test_flushes_session(self) -> None:
        session = _make_mock_session()
        mock_thread = _make_mock_thread(message_count=3)
        mock_msg = _make_mock_message()
        mock_tm = _make_mock_thread_message(mock_msg)

        thread_result = MagicMock()
        thread_result.scalar_one_or_none.return_value = mock_thread
        tms_result = MagicMock()
        tms_scalars = MagicMock()
        tms_scalars.all.return_value = [mock_tm]
        tms_result.scalars.return_value = tms_scalars

        session.execute.side_effect = [thread_result, tms_result]

        with patch("app.services.knowledge.extract_nuggets", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = [{"title": "T", "content": "C", "tags": []}]
            await process_thread_for_nuggets(
                session=session,
                thread_id=THREAD_ID,
                user_id=USER_ID,
                model=MODEL,
                api_key=API_KEY,
            )

        assert session.flush.called
