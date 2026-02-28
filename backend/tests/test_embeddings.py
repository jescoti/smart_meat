"""Tests for the embedding service.

TDD RED phase — tests written before implementation.
Tests embedding generation, batch processing, and skip-existing logic.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

# Test constants
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GROUP_ID = uuid.UUID("660e8400-e29b-41d4-a716-446655440000")
MESSAGE_ID_1 = uuid.UUID("880e8400-e29b-41d4-a716-446655440001")
MESSAGE_ID_2 = uuid.UUID("880e8400-e29b-41d4-a716-446655440002")
MESSAGE_ID_3 = uuid.UUID("880e8400-e29b-41d4-a716-446655440003")


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_mock_message(
    *,
    message_id: uuid.UUID = MESSAGE_ID_1,
    subject: str = "Test Subject",
    body_text: str | None = "Test body text content",
    processing_status: str = "threaded",
    embedding: object | None = None,
) -> MagicMock:
    """Create a mock Message object."""
    msg = MagicMock()
    msg.id = message_id
    msg.subject = subject
    msg.body_text = body_text
    msg.processing_status = processing_status
    msg.embedding = embedding
    return msg


class TestGenerateEmbedding:
    """Tests for generate_embedding function."""

    async def test_returns_list_of_floats(self) -> None:
        """generate_embedding should return a list of floats."""
        from app.services.embeddings import generate_embedding

        result = await generate_embedding("hello world")

        assert isinstance(result, list)
        assert len(result) == 384
        assert all(isinstance(v, float) for v in result)

    async def test_deterministic_for_same_input(self) -> None:
        """Same input should produce the same embedding."""
        from app.services.embeddings import generate_embedding

        result1 = await generate_embedding("hello world")
        result2 = await generate_embedding("hello world")

        assert result1 == result2

    async def test_different_input_produces_different_embedding(self) -> None:
        """Different inputs should produce different embeddings."""
        from app.services.embeddings import generate_embedding

        result1 = await generate_embedding("hello world")
        result2 = await generate_embedding("goodbye world")

        assert result1 != result2

    async def test_empty_string_produces_embedding(self) -> None:
        """Empty string should still produce a valid embedding."""
        from app.services.embeddings import generate_embedding

        result = await generate_embedding("")

        assert isinstance(result, list)
        assert len(result) == 384

    async def test_values_are_normalized(self) -> None:
        """Embedding values should be normalized (unit vector)."""
        import math

        from app.services.embeddings import generate_embedding

        result = await generate_embedding("test text")

        magnitude = math.sqrt(sum(v * v for v in result))
        assert abs(magnitude - 1.0) < 1e-6

    async def test_default_model_name(self) -> None:
        """Default model_name should be accepted without error."""
        from app.services.embeddings import generate_embedding

        result = await generate_embedding("test", model_name="text-embedding-3-small")

        assert len(result) == 384

    async def test_custom_model_name_accepted(self) -> None:
        """Custom model_name should be accepted."""
        from app.services.embeddings import generate_embedding

        result = await generate_embedding("test", model_name="custom-model")

        assert len(result) == 384


class TestGenerateEmbeddingsForMessages:
    """Tests for generate_embeddings_for_messages function."""

    async def test_returns_count_of_generated_embeddings(self) -> None:
        """Should return the count of embeddings generated."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg1 = _make_mock_message(message_id=MESSAGE_ID_1)
        msg2 = _make_mock_message(message_id=MESSAGE_ID_2)

        # Mock scalars().all() to return messages
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg1, msg2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        count = await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1, MESSAGE_ID_2],
        )

        assert count == 2

    async def test_skips_messages_with_existing_embeddings(self) -> None:
        """Should skip messages that already have embeddings."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        existing_embedding = MagicMock()
        msg1 = _make_mock_message(message_id=MESSAGE_ID_1, embedding=existing_embedding)
        msg2 = _make_mock_message(message_id=MESSAGE_ID_2, embedding=None)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg1, msg2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        count = await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1, MESSAGE_ID_2],
        )

        assert count == 1

    async def test_updates_processing_status_to_embedded(self) -> None:
        """Should update processing_status to 'embedded' for processed messages."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(message_id=MESSAGE_ID_1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        assert msg.processing_status == "embedded"

    async def test_stores_embedding_in_session(self) -> None:
        """Should add MessageEmbedding objects to the session."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(message_id=MESSAGE_ID_1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        session.add.assert_called_once()

    async def test_concatenates_subject_and_body(self) -> None:
        """Should concatenate subject and body_text for embedding generation."""
        from app.services.embeddings import generate_embedding, generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(
            message_id=MESSAGE_ID_1,
            subject="Important Meeting",
            body_text="Please attend the meeting tomorrow.",
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        # Verify the embedding was generated from subject + body
        expected_text = "Important Meeting\nPlease attend the meeting tomorrow."
        expected_embedding = await generate_embedding(expected_text)

        added_obj = session.add.call_args[0][0]
        assert list(added_obj.embedding) == expected_embedding

    async def test_handles_none_body_text(self) -> None:
        """Should handle messages with None body_text."""
        from app.services.embeddings import generate_embedding, generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(
            message_id=MESSAGE_ID_1,
            subject="Subject Only",
            body_text=None,
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        expected_text = "Subject Only\n"
        expected_embedding = await generate_embedding(expected_text)

        added_obj = session.add.call_args[0][0]
        assert list(added_obj.embedding) == expected_embedding

    async def test_empty_message_ids_returns_zero(self) -> None:
        """Should return 0 when given an empty list of message IDs."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        count = await generate_embeddings_for_messages(
            session=session,
            message_ids=[],
        )

        assert count == 0

    async def test_flushes_session_after_processing(self) -> None:
        """Should flush the session after processing all messages."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(message_id=MESSAGE_ID_1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        session.flush.assert_awaited_once()

    async def test_all_messages_skipped_no_flush(self) -> None:
        """Should not flush when all messages already have embeddings."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        existing_embedding = MagicMock()
        msg = _make_mock_message(message_id=MESSAGE_ID_1, embedding=existing_embedding)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        count = await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        assert count == 0
        session.flush.assert_not_awaited()

    async def test_embedding_object_has_correct_message_id(self) -> None:
        """The stored MessageEmbedding should have the correct message_id."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg = _make_mock_message(message_id=MESSAGE_ID_1)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1],
        )

        added_obj = session.add.call_args[0][0]
        assert added_obj.message_id == MESSAGE_ID_1

    async def test_multiple_messages_processed(self) -> None:
        """Should process multiple messages and return correct count."""
        from app.services.embeddings import generate_embeddings_for_messages

        session = _make_mock_session()

        msg1 = _make_mock_message(message_id=MESSAGE_ID_1, subject="Subject 1")
        msg2 = _make_mock_message(message_id=MESSAGE_ID_2, subject="Subject 2")
        msg3 = _make_mock_message(message_id=MESSAGE_ID_3, subject="Subject 3")

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [msg1, msg2, msg3]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        session.execute = AsyncMock(return_value=mock_result)

        count = await generate_embeddings_for_messages(
            session=session,
            message_ids=[MESSAGE_ID_1, MESSAGE_ID_2, MESSAGE_ID_3],
        )

        assert count == 3
        assert session.add.call_count == 3
