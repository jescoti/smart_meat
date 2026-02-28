"""Tests for the search service.

TDD RED phase — tests written before implementation.
Tests query construction, filtering, pagination, empty results, and ranking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
OTHER_GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440099")
THREAD_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
MESSAGE_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_mock_row(
    *,
    message_id: uuid.UUID = MESSAGE_ID_1,
    subject: str = "Test Subject",
    sender_name: str | None = "Alice",
    sender_email: str = "alice@example.com",
    gmail_date: datetime | None = None,
    body_text: str | None = "Hello, this is the message body that is long enough.",
    group_id: uuid.UUID = GROUP_ID,
    thread_id: uuid.UUID | None = THREAD_ID,
    rank: float = 0.5,
) -> MagicMock:
    """Create a mock database row for search results.

    Simulates the shape returned by the search query:
    Row(message_id, subject, sender_name, sender_email, gmail_date, body_text,
        group_id, thread_id, rank).
    """
    row = MagicMock()
    row.message_id = message_id
    row.subject = subject
    row.sender_name = sender_name
    row.sender_email = sender_email
    row.gmail_date = gmail_date or datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
    row.body_text = body_text
    row.group_id = group_id
    row.thread_id = thread_id
    row.rank = rank
    return row


class TestSearchMessages:
    """Tests for search_messages function."""

    async def test_returns_search_result_dataclass(self) -> None:
        """search_messages should return a SearchResult with correct fields."""
        from app.services.search import SearchResult, search_messages

        session = _make_mock_session()
        # Count query returns 0
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        # Results query returns empty
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert isinstance(result, SearchResult)
        assert result.results == []
        assert result.total == 0
        assert result.page == 1
        assert result.per_page == 20

    async def test_returns_message_search_hits(self) -> None:
        """search_messages should return MessageSearchHit items in results."""
        from app.services.search import MessageSearchHit, search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(
            subject="Meeting Notes",
            sender_name="Bob",
            sender_email="bob@example.com",
            body_text="Notes from our weekly meeting about project updates.",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.75,
        )
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="meeting",
        )

        assert len(result.results) == 1
        hit = result.results[0]
        assert isinstance(hit, MessageSearchHit)
        assert hit.message_id == MESSAGE_ID_1
        assert hit.subject == "Meeting Notes"
        assert hit.sender_name == "Bob"
        assert hit.sender_email == "bob@example.com"
        assert hit.group_id == GROUP_ID
        assert hit.thread_id == THREAD_ID
        assert hit.rank == 0.75

    async def test_snippet_truncated_to_200_chars(self) -> None:
        """Snippet should be first 200 characters of body_text."""
        from app.services.search import search_messages

        long_body = "A" * 300
        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(body_text=long_body)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert len(result.results[0].snippet) == 200

    async def test_snippet_handles_none_body(self) -> None:
        """Snippet should be empty string when body_text is None."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(body_text=None)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].snippet == ""

    async def test_snippet_short_body_not_truncated(self) -> None:
        """Snippet should not be truncated when body_text is shorter than 200 chars."""
        from app.services.search import search_messages

        short_body = "Short message body"
        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(body_text=short_body)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].snippet == short_body

    async def test_pagination_defaults(self) -> None:
        """Default page=1, per_page=20."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.page == 1
        assert result.per_page == 20

    async def test_pagination_custom_values(self) -> None:
        """Custom page and per_page should be returned in result."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            page=3,
            per_page=10,
        )

        assert result.page == 3
        assert result.per_page == 10
        assert result.total == 50

    async def test_filter_by_group_id(self) -> None:
        """Passing group_id should filter results to that group."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(group_id=GROUP_ID)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            group_id=GROUP_ID,
        )

        # The service should have executed queries — we verify it accepted the filter
        assert session.execute.call_count == 2
        assert result.total == 1

    async def test_filter_by_sender_email(self) -> None:
        """Passing sender_email should filter results."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(sender_email="alice@example.com")
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            sender_email="alice@example.com",
        )

        assert session.execute.call_count == 2
        assert result.results[0].sender_email == "alice@example.com"

    async def test_filter_by_date_from(self) -> None:
        """Passing date_from should filter messages after that date."""
        from app.services.search import search_messages

        session = _make_mock_session()
        date_from = datetime(2024, 1, 1, tzinfo=UTC)

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            date_from=date_from,
        )

        assert session.execute.call_count == 2
        assert result.total == 0

    async def test_filter_by_date_to(self) -> None:
        """Passing date_to should filter messages before that date."""
        from app.services.search import search_messages

        session = _make_mock_session()
        date_to = datetime(2024, 12, 31, tzinfo=UTC)

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            date_to=date_to,
        )

        assert session.execute.call_count == 2
        assert result.total == 0

    async def test_all_filters_combined(self) -> None:
        """All filters can be used simultaneously."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
            group_id=GROUP_ID,
            sender_email="alice@example.com",
            date_from=datetime(2024, 1, 1, tzinfo=UTC),
            date_to=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert session.execute.call_count == 2
        assert result.total == 0

    async def test_empty_results(self) -> None:
        """No matches should return empty results list."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="nonexistent",
        )

        assert result.results == []
        assert result.total == 0

    async def test_multiple_results_ordered_by_rank(self) -> None:
        """Multiple results should be present; ordering is by rank (from DB)."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 2

        row1 = _make_mock_row(
            message_id=MESSAGE_ID_1,
            subject="First Result",
            rank=0.9,
        )
        row2 = _make_mock_row(
            message_id=MESSAGE_ID_2,
            subject="Second Result",
            rank=0.5,
        )
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [row1, row2]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert len(result.results) == 2
        assert result.results[0].rank == 0.9
        assert result.results[1].rank == 0.5

    async def test_thread_id_none_when_no_thread(self) -> None:
        """thread_id should be None when the message has no thread association."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(thread_id=None)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].thread_id is None

    async def test_gmail_date_preserved(self) -> None:
        """gmail_date should be preserved from the database row."""
        from app.services.search import search_messages

        session = _make_mock_session()
        dt = datetime(2024, 3, 15, 14, 30, tzinfo=UTC)

        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(gmail_date=dt)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].gmail_date == dt

    async def test_sender_name_none(self) -> None:
        """sender_name can be None."""
        from app.services.search import search_messages

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(sender_name=None)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await search_messages(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].sender_name is None


class TestSearchResultDataclass:
    """Tests for SearchResult and MessageSearchHit dataclasses."""

    def test_search_result_fields(self) -> None:
        """SearchResult should have results, total, page, per_page fields."""
        from app.services.search import MessageSearchHit, SearchResult

        hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Test",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=datetime(2024, 1, 1, tzinfo=UTC),
            snippet="snippet",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.5,
        )
        result = SearchResult(
            results=[hit],
            total=1,
            page=1,
            per_page=20,
        )

        assert result.results == [hit]
        assert result.total == 1
        assert result.page == 1
        assert result.per_page == 20

    def test_message_search_hit_fields(self) -> None:
        """MessageSearchHit should have all required fields."""
        from app.services.search import MessageSearchHit

        hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Meeting Notes",
            sender_name="Bob",
            sender_email="bob@example.com",
            gmail_date=datetime(2024, 1, 15, tzinfo=UTC),
            snippet="Notes from our weekly...",
            group_id=GROUP_ID,
            thread_id=None,
            rank=0.8,
        )

        assert hit.message_id == MESSAGE_ID_1
        assert hit.subject == "Meeting Notes"
        assert hit.sender_name == "Bob"
        assert hit.sender_email == "bob@example.com"
        assert hit.snippet == "Notes from our weekly..."
        assert hit.group_id == GROUP_ID
        assert hit.thread_id is None
        assert hit.rank == 0.8
