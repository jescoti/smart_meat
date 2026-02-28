"""Tests for semantic and combined search.

TDD RED phase — tests written before implementation.
Tests semantic search, combined search with deduplication and weighted scoring.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
THREAD_ID = uuid.UUID("770e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
MESSAGE_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")
MESSAGE_ID_3 = uuid.UUID("880e8400-e29b-41d4-a716-446655440003")


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
    body_text: str | None = "Hello, this is the message body.",
    group_id: uuid.UUID = GROUP_ID,
    thread_id: uuid.UUID | None = THREAD_ID,
    cosine_distance: float = 0.2,
) -> MagicMock:
    """Create a mock database row for semantic search results."""
    row = MagicMock()
    row.message_id = message_id
    row.subject = subject
    row.sender_name = sender_name
    row.sender_email = sender_email
    row.gmail_date = gmail_date or datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
    row.body_text = body_text
    row.group_id = group_id
    row.thread_id = thread_id
    row.cosine_distance = cosine_distance
    return row


class TestSemanticSearch:
    """Tests for semantic_search function."""

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_returns_search_result_dataclass(self, mock_embed: AsyncMock) -> None:
        """semantic_search should return a SearchResult."""
        from app.services.search import SearchResult, semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test query",
        )

        assert isinstance(result, SearchResult)
        assert result.results == []
        assert result.total == 0

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_generates_embedding_for_query(self, mock_embed: AsyncMock) -> None:
        """Should generate an embedding for the query text."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        await semantic_search(
            session=session,
            user_id=USER_ID,
            query="semantic query text",
        )

        mock_embed.assert_awaited_once_with("semantic query text")

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_returns_results_ranked_by_similarity(self, mock_embed: AsyncMock) -> None:
        """Results should be ranked by cosine similarity (1 - distance)."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 2

        row1 = _make_mock_row(
            message_id=MESSAGE_ID_1,
            subject="Very Relevant",
            cosine_distance=0.1,
        )
        row2 = _make_mock_row(
            message_id=MESSAGE_ID_2,
            subject="Less Relevant",
            cosine_distance=0.5,
        )
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [row1, row2]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert len(result.results) == 2
        # Rank is 1 - cosine_distance (similarity)
        assert result.results[0].rank == pytest.approx(0.9)
        assert result.results[1].rank == pytest.approx(0.5)

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_pagination_defaults(self, mock_embed: AsyncMock) -> None:
        """Default page=1, per_page=20."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.page == 1
        assert result.per_page == 20

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_custom_pagination(self, mock_embed: AsyncMock) -> None:
        """Custom page and per_page should be honored."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 50
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
            page=3,
            per_page=10,
        )

        assert result.page == 3
        assert result.per_page == 10
        assert result.total == 50

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_filter_by_group_id(self, mock_embed: AsyncMock) -> None:
        """Passing group_id should filter results."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_row = _make_mock_row(group_id=GROUP_ID)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
            group_id=GROUP_ID,
        )

        assert session.execute.call_count == 2
        assert result.total == 1

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_filter_by_sender_email(self, mock_embed: AsyncMock) -> None:
        """Passing sender_email should filter results."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1
        mock_row = _make_mock_row(sender_email="alice@example.com")
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
            sender_email="alice@example.com",
        )

        assert session.execute.call_count == 2
        assert result.results[0].sender_email == "alice@example.com"

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_filter_by_date_range(self, mock_embed: AsyncMock) -> None:
        """date_from and date_to should filter results."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
            date_from=datetime(2024, 1, 1, tzinfo=UTC),
            date_to=datetime(2024, 12, 31, tzinfo=UTC),
        )

        assert session.execute.call_count == 2
        assert result.total == 0

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_snippet_from_body_text(self, mock_embed: AsyncMock) -> None:
        """Snippet should be first 200 chars of body_text."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        long_body = "A" * 300
        mock_row = _make_mock_row(body_text=long_body, cosine_distance=0.2)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert len(result.results[0].snippet) == 200

    @patch("app.services.search.generate_embedding", new_callable=AsyncMock)
    async def test_none_body_text_snippet(self, mock_embed: AsyncMock) -> None:
        """None body_text should produce empty snippet."""
        from app.services.search import semantic_search

        mock_embed.return_value = [0.1] * 384

        session = _make_mock_session()
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        mock_row = _make_mock_row(body_text=None, cosine_distance=0.2)
        mock_results_result = MagicMock()
        mock_results_result.all.return_value = [mock_row]

        session.execute = AsyncMock(side_effect=[mock_count_result, mock_results_result])

        result = await semantic_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].snippet == ""


class TestCombinedSearch:
    """Tests for combined_search function."""

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_returns_search_result(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """combined_search should return a SearchResult."""
        from app.services.search import SearchResult, combined_search

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=20)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=20)

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert isinstance(result, SearchResult)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_calls_both_fts_and_semantic(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Should call both FTS and semantic search."""
        from app.services.search import SearchResult, combined_search

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=20)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=20)

        session = _make_mock_session()
        await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        mock_fts.assert_awaited_once()
        mock_semantic.assert_awaited_once()

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_weighted_scoring(self, mock_fts: AsyncMock, mock_semantic: AsyncMock) -> None:
        """Combined score should be 0.7 * FTS_rank + 0.3 * semantic_rank."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        fts_hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Test",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="snippet",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.8,
        )
        semantic_hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Test",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="snippet",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.6,
        )

        mock_fts.return_value = SearchResult(results=[fts_hit], total=1, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(
            results=[semantic_hit], total=1, page=1, per_page=100
        )

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        # 0.7 * 0.8 + 0.3 * 0.6 = 0.56 + 0.18 = 0.74
        assert len(result.results) == 1
        assert result.results[0].rank == pytest.approx(0.74)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_deduplication_keeps_highest_score(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Duplicate message_ids should be deduplicated, keeping highest combined score."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        fts_hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Test",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="fts snippet",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.9,
        )

        semantic_hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Test",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="semantic snippet",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.7,
        )

        mock_fts.return_value = SearchResult(results=[fts_hit], total=1, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(
            results=[semantic_hit], total=1, page=1, per_page=100
        )

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        # Should be deduplicated to 1 result
        assert len(result.results) == 1
        # Combined: 0.7 * 0.9 + 0.3 * 0.7 = 0.63 + 0.21 = 0.84
        assert result.results[0].rank == pytest.approx(0.84)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_unique_results_from_both_sources(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Results unique to FTS or semantic should both appear."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        fts_only = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="FTS Only",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="fts",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.8,
        )
        semantic_only = MessageSearchHit(
            message_id=MESSAGE_ID_2,
            subject="Semantic Only",
            sender_name="Bob",
            sender_email="bob@example.com",
            gmail_date=dt,
            snippet="semantic",
            group_id=GROUP_ID,
            thread_id=None,
            rank=0.6,
        )

        mock_fts.return_value = SearchResult(results=[fts_only], total=1, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(
            results=[semantic_only], total=1, page=1, per_page=100
        )

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert len(result.results) == 2
        # FTS-only: 0.7 * 0.8 = 0.56
        # Semantic-only: 0.3 * 0.6 = 0.18
        # Sorted by combined score descending
        assert result.results[0].rank == pytest.approx(0.56)
        assert result.results[1].rank == pytest.approx(0.18)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_sorted_by_combined_score_descending(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Results should be sorted by combined score descending."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        fts_hit1 = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="Low FTS",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.3,
        )
        fts_hit2 = MessageSearchHit(
            message_id=MESSAGE_ID_2,
            subject="High FTS",
            sender_name="Bob",
            sender_email="bob@example.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=None,
            rank=0.9,
        )

        semantic_hit1 = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="High Semantic",
            sender_name="Alice",
            sender_email="alice@example.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=THREAD_ID,
            rank=0.9,
        )
        semantic_hit2 = MessageSearchHit(
            message_id=MESSAGE_ID_3,
            subject="Semantic Only",
            sender_name="Carol",
            sender_email="carol@example.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=None,
            rank=0.5,
        )

        mock_fts.return_value = SearchResult(
            results=[fts_hit1, fts_hit2], total=2, page=1, per_page=100
        )
        mock_semantic.return_value = SearchResult(
            results=[semantic_hit1, semantic_hit2], total=2, page=1, per_page=100
        )

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        # MSG1: 0.7*0.3 + 0.3*0.9 = 0.21 + 0.27 = 0.48
        # MSG2: 0.7*0.9 + 0.3*0 = 0.63 (FTS only)
        # MSG3: 0.7*0 + 0.3*0.5 = 0.15 (semantic only)
        assert len(result.results) == 3
        assert result.results[0].rank == pytest.approx(0.63)
        assert result.results[1].rank == pytest.approx(0.48)
        assert result.results[2].rank == pytest.approx(0.15)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_pagination_applied_to_combined_results(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Pagination should be applied to the combined results."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)

        # Create 3 unique results
        hits = []
        for i, mid in enumerate([MESSAGE_ID_1, MESSAGE_ID_2, MESSAGE_ID_3]):
            hits.append(
                MessageSearchHit(
                    message_id=mid,
                    subject=f"Result {i}",
                    sender_name="Alice",
                    sender_email="alice@example.com",
                    gmail_date=dt,
                    snippet="s",
                    group_id=GROUP_ID,
                    thread_id=THREAD_ID,
                    rank=0.9 - (i * 0.2),
                )
            )

        mock_fts.return_value = SearchResult(results=hits, total=3, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=100)

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
            page=2,
            per_page=1,
        )

        # Page 2 with per_page=1 should get the second result
        assert len(result.results) == 1
        assert result.page == 2
        assert result.per_page == 1
        assert result.total == 3

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_empty_results_from_both(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """When both searches return empty, combined should return empty."""
        from app.services.search import SearchResult, combined_search

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=20)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=20)

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="nothing",
        )

        assert result.results == []
        assert result.total == 0

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_passes_filters_to_both_searches(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Filters should be passed to both FTS and semantic search."""
        from app.services.search import SearchResult, combined_search

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=100)

        session = _make_mock_session()
        date_from = datetime(2024, 1, 1, tzinfo=UTC)
        date_to = datetime(2024, 12, 31, tzinfo=UTC)

        await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
            group_id=GROUP_ID,
            sender_email="alice@example.com",
            date_from=date_from,
            date_to=date_to,
        )

        # Verify FTS call has filters
        fts_kwargs = mock_fts.call_args.kwargs
        assert fts_kwargs["group_id"] == GROUP_ID
        assert fts_kwargs["sender_email"] == "alice@example.com"
        assert fts_kwargs["date_from"] == date_from
        assert fts_kwargs["date_to"] == date_to

        # Verify semantic call has filters
        sem_kwargs = mock_semantic.call_args.kwargs
        assert sem_kwargs["group_id"] == GROUP_ID
        assert sem_kwargs["sender_email"] == "alice@example.com"
        assert sem_kwargs["date_from"] == date_from
        assert sem_kwargs["date_to"] == date_to

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_uses_large_per_page_for_sub_queries(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """Sub-queries should use a large per_page to get all results before pagination."""
        from app.services.search import SearchResult, combined_search

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=100)

        session = _make_mock_session()
        await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
            page=1,
            per_page=10,
        )

        # Both sub-queries should use page=1 and a large per_page
        fts_kwargs = mock_fts.call_args.kwargs
        assert fts_kwargs["page"] == 1
        assert fts_kwargs["per_page"] == 100

        sem_kwargs = mock_semantic.call_args.kwargs
        assert sem_kwargs["page"] == 1
        assert sem_kwargs["per_page"] == 100

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_fts_only_hit_gets_weighted_fts_score(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """A hit only in FTS should have combined score = 0.7 * fts_rank."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
        fts_hit = MessageSearchHit(
            message_id=MESSAGE_ID_1,
            subject="FTS Only",
            sender_name="A",
            sender_email="a@b.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=None,
            rank=1.0,
        )

        mock_fts.return_value = SearchResult(results=[fts_hit], total=1, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(results=[], total=0, page=1, per_page=100)

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].rank == pytest.approx(0.7)

    @patch("app.services.search.semantic_search", new_callable=AsyncMock)
    @patch("app.services.search.search_messages", new_callable=AsyncMock)
    async def test_semantic_only_hit_gets_weighted_semantic_score(
        self, mock_fts: AsyncMock, mock_semantic: AsyncMock
    ) -> None:
        """A hit only in semantic should have combined score = 0.3 * semantic_rank."""
        from app.services.search import MessageSearchHit, SearchResult, combined_search

        dt = datetime(2024, 1, 12, 9, 0, tzinfo=UTC)
        semantic_hit = MessageSearchHit(
            message_id=MESSAGE_ID_2,
            subject="Semantic Only",
            sender_name="B",
            sender_email="b@c.com",
            gmail_date=dt,
            snippet="s",
            group_id=GROUP_ID,
            thread_id=None,
            rank=1.0,
        )

        mock_fts.return_value = SearchResult(results=[], total=0, page=1, per_page=100)
        mock_semantic.return_value = SearchResult(
            results=[semantic_hit], total=1, page=1, per_page=100
        )

        session = _make_mock_session()
        result = await combined_search(
            session=session,
            user_id=USER_ID,
            query="test",
        )

        assert result.results[0].rank == pytest.approx(0.3)
