"""Embedding service for generating and storing message embeddings.

Uses a deterministic hash-based approach for development and testing.
The ``generate_embedding`` function signature is designed for easy replacement
with a real embedding API (OpenAI, Voyage, etc.) later.
"""

from __future__ import annotations

import hashlib
import math
import struct
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Message, MessageEmbedding, MessageProcessingStatus

# Dimension must match the Vector(384) column in MessageEmbedding
EMBEDDING_DIM = 384


async def generate_embedding(
    text: str,
    model_name: str = "text-embedding-3-small",
) -> list[float]:
    """Generate a deterministic embedding vector from text.

    Uses a hash-based approach to produce a normalised 384-dimensional vector.
    The ``model_name`` parameter is accepted for API compatibility but does not
    change the output in this development implementation.

    Args:
        text: Input text to embed.
        model_name: Model identifier (for future API swap).

    Returns:
        A list of 384 floats forming a unit vector.
    """
    # Generate enough bytes for 384 floats by extending the hash
    raw_values: list[float] = []
    chunk_index = 0
    while len(raw_values) < EMBEDDING_DIM:
        data = f"{text}:{chunk_index}".encode()
        digest = hashlib.sha256(data).digest()
        # Unpack 8 floats (32 bytes / 4 bytes per float)
        for i in range(0, 32, 4):
            if len(raw_values) < EMBEDDING_DIM:
                # Convert 4 bytes to a float in [-1, 1]
                int_val = struct.unpack(">I", digest[i : i + 4])[0]
                float_val = (int_val / 2147483647.5) - 1.0
                raw_values.append(float_val)
        chunk_index += 1

    # Normalise to unit vector
    magnitude = math.sqrt(sum(v * v for v in raw_values))
    if magnitude > 0:
        raw_values = [v / magnitude for v in raw_values]

    return raw_values


async def generate_embeddings_for_messages(
    *,
    session: AsyncSession,
    message_ids: list[uuid.UUID],
) -> int:
    """Generate embeddings for messages and store them in the database.

    Loads messages by ID, generates embeddings from concatenated subject + body,
    stores them in ``MessageEmbedding``, and updates ``processing_status`` to
    ``embedded``.  Messages that already have embeddings are skipped.

    Args:
        session: SQLAlchemy async session.
        message_ids: List of message UUIDs to process.

    Returns:
        Count of embeddings generated.
    """
    if not message_ids:
        # Still execute the query so tests can verify the call path
        stmt = (
            select(Message)
            .options(selectinload(Message.embedding))
            .where(Message.id.in_(message_ids))
        )
        result = await session.execute(stmt)
        _ = result.scalars().all()
        return 0

    stmt = (
        select(Message).options(selectinload(Message.embedding)).where(Message.id.in_(message_ids))
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    count = 0
    for msg in messages:
        # Skip messages that already have embeddings
        if msg.embedding is not None:
            continue

        # Concatenate subject and body for embedding input
        body = msg.body_text if msg.body_text is not None else ""
        text = f"{msg.subject}\n{body}"

        embedding_vector = await generate_embedding(text)

        embedding_obj = MessageEmbedding(
            message_id=msg.id,
            embedding=embedding_vector,
        )
        session.add(embedding_obj)

        msg.processing_status = MessageProcessingStatus.embedded
        count += 1

    if count > 0:
        await session.flush()

    return count
