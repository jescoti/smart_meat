"""Search service for messages — full-text, semantic, and combined search.

Full-text search uses PostgreSQL ``websearch_to_tsquery`` with ``ts_rank_cd``.
Semantic search uses pgvector cosine distance on message embeddings.
Combined search merges both with 0.7/0.3 weighting.

All queries are parameterised — user input is never interpolated into SQL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, Message, MessageEmbedding, ThreadMessage
from app.services.embeddings import generate_embedding


@dataclass(frozen=True)
class MessageSearchHit:
    """A single search result item."""

    message_id: uuid.UUID
    subject: str
    sender_name: str | None
    sender_email: str
    gmail_date: datetime
    snippet: str
    group_id: uuid.UUID
    thread_id: uuid.UUID | None
    rank: float


@dataclass(frozen=True)
class SearchResult:
    """Paginated search results."""

    results: list[MessageSearchHit]
    total: int
    page: int
    per_page: int


def _build_snippet(body_text: str | None) -> str:
    """Return the first 200 characters of body_text, or empty string if None."""
    if body_text is None:
        return ""
    return body_text[:200]


async def search_messages(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    group_id: uuid.UUID | None = None,
    sender_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> SearchResult:
    """Search messages via PostgreSQL full-text search.

    Only returns messages from groups owned by the given user.  Filters are
    all optional and can be combined.

    Args:
        session: SQLAlchemy async session.
        user_id: The authenticated user's UUID (for ownership check).
        query: Search query string (passed to ``websearch_to_tsquery``).
        group_id: Optional — restrict to a specific group.
        sender_email: Optional — filter by sender email address.
        date_from: Optional — messages on or after this date.
        date_to: Optional — messages on or before this date.
        page: Page number (1-based).
        per_page: Results per page.

    Returns:
        SearchResult with matching messages and pagination info.
    """
    # Build the ts_query expression
    ts_query = func.websearch_to_tsquery("english", query)
    ts_vector = func.to_tsvector("english", func.coalesce(Message.body_text, ""))

    # Base WHERE conditions: FTS match + group ownership
    conditions = [
        ts_vector.op("@@")(ts_query),
        Group.owner_id == user_id,
    ]

    # Optional filters
    if group_id is not None:
        conditions.append(Message.group_id == group_id)
    if sender_email is not None:
        conditions.append(Message.sender_email == sender_email)
    if date_from is not None:
        conditions.append(Message.date >= date_from)
    if date_to is not None:
        conditions.append(Message.date <= date_to)

    # Count query
    count_stmt = (
        select(func.count(Message.id))
        .join(Group, Message.group_id == Group.id)
        .outerjoin(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(*conditions)
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # Results query with ranking
    rank_expr = func.ts_rank_cd(ts_vector, ts_query)

    results_stmt = (
        select(
            Message.id.label("message_id"),
            Message.subject,
            Message.sender_name,
            Message.sender_email,
            Message.date.label("gmail_date"),
            Message.body_text,
            Message.group_id,
            ThreadMessage.thread_id,
            rank_expr.label("rank"),
        )
        .join(Group, Message.group_id == Group.id)
        .outerjoin(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(*conditions)
        .order_by(rank_expr.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows_result = await session.execute(results_stmt)
    rows = rows_result.all()

    hits = [
        MessageSearchHit(
            message_id=row.message_id,
            subject=row.subject,
            sender_name=row.sender_name,
            sender_email=row.sender_email,
            gmail_date=row.gmail_date,
            snippet=_build_snippet(row.body_text),
            group_id=row.group_id,
            thread_id=row.thread_id,
            rank=row.rank,
        )
        for row in rows
    ]

    return SearchResult(
        results=hits,
        total=total,
        page=page,
        per_page=per_page,
    )


async def semantic_search(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    group_id: uuid.UUID | None = None,
    sender_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> SearchResult:
    """Search messages using pgvector cosine distance on embeddings.

    Generates an embedding for the query text, then searches the
    ``MessageEmbedding`` table using the ``<=>`` cosine distance operator.
    Only returns messages from groups owned by the given user.

    Args:
        session: SQLAlchemy async session.
        user_id: The authenticated user's UUID (for ownership check).
        query: Search query string to embed and compare.
        group_id: Optional — restrict to a specific group.
        sender_email: Optional — filter by sender email address.
        date_from: Optional — messages on or after this date.
        date_to: Optional — messages on or before this date.
        page: Page number (1-based).
        per_page: Results per page.

    Returns:
        SearchResult with matching messages ranked by cosine similarity.
    """
    query_embedding = await generate_embedding(query)

    # Cosine distance expression
    cosine_dist = MessageEmbedding.embedding.cosine_distance(query_embedding)

    # Base WHERE conditions: group ownership via join
    conditions: list[object] = [
        Group.owner_id == user_id,
    ]

    # Optional filters
    if group_id is not None:
        conditions.append(Message.group_id == group_id)
    if sender_email is not None:
        conditions.append(Message.sender_email == sender_email)
    if date_from is not None:
        conditions.append(Message.date >= date_from)
    if date_to is not None:
        conditions.append(Message.date <= date_to)

    # Count query
    count_stmt = (
        select(func.count(Message.id))
        .join(MessageEmbedding, MessageEmbedding.message_id == Message.id)
        .join(Group, Message.group_id == Group.id)
        .outerjoin(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(*conditions)
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    # Results query ranked by cosine distance (ascending = most similar first)
    results_stmt = (
        select(
            Message.id.label("message_id"),
            Message.subject,
            Message.sender_name,
            Message.sender_email,
            Message.date.label("gmail_date"),
            Message.body_text,
            Message.group_id,
            ThreadMessage.thread_id,
            cosine_dist.label("cosine_distance"),
        )
        .join(MessageEmbedding, MessageEmbedding.message_id == Message.id)
        .join(Group, Message.group_id == Group.id)
        .outerjoin(ThreadMessage, ThreadMessage.message_id == Message.id)
        .where(*conditions)
        .order_by(cosine_dist.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows_result = await session.execute(results_stmt)
    rows = rows_result.all()

    hits = [
        MessageSearchHit(
            message_id=row.message_id,
            subject=row.subject,
            sender_name=row.sender_name,
            sender_email=row.sender_email,
            gmail_date=row.gmail_date,
            snippet=_build_snippet(row.body_text),
            group_id=row.group_id,
            thread_id=row.thread_id,
            rank=1.0 - row.cosine_distance,
        )
        for row in rows
    ]

    return SearchResult(
        results=hits,
        total=total,
        page=page,
        per_page=per_page,
    )


# Maximum number of results to fetch from each sub-search for combining
_COMBINED_SUB_QUERY_LIMIT = 100

# Weighting factors for combined scoring
_FTS_WEIGHT = 0.7
_SEMANTIC_WEIGHT = 0.3


async def combined_search(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    group_id: uuid.UUID | None = None,
    sender_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> SearchResult:
    """Combined FTS + semantic search with weighted scoring.

    Runs both full-text search and semantic search, merges results with
    weighted scoring (0.7 * FTS rank + 0.3 * semantic rank), deduplicates
    by message_id, and applies pagination.

    Args:
        session: SQLAlchemy async session.
        user_id: The authenticated user's UUID.
        query: Search query string.
        group_id: Optional — restrict to a specific group.
        sender_email: Optional — filter by sender email address.
        date_from: Optional — messages on or after this date.
        date_to: Optional — messages on or before this date.
        page: Page number (1-based).
        per_page: Results per page.

    Returns:
        SearchResult with merged, weighted, and deduplicated results.
    """
    filter_kwargs: dict[str, uuid.UUID | str | datetime | int | None] = {
        "group_id": group_id,
        "sender_email": sender_email,
        "date_from": date_from,
        "date_to": date_to,
        "page": 1,
        "per_page": _COMBINED_SUB_QUERY_LIMIT,
    }

    fts_result = await search_messages(
        session=session,
        user_id=user_id,
        query=query,
        **filter_kwargs,  # type: ignore[arg-type]
    )

    sem_result = await semantic_search(
        session=session,
        user_id=user_id,
        query=query,
        **filter_kwargs,  # type: ignore[arg-type]
    )

    # Build score maps: message_id -> (fts_rank, semantic_rank)
    fts_scores: dict[uuid.UUID, float] = {}
    fts_hits: dict[uuid.UUID, MessageSearchHit] = {}
    for hit in fts_result.results:
        fts_scores[hit.message_id] = hit.rank
        fts_hits[hit.message_id] = hit

    sem_scores: dict[uuid.UUID, float] = {}
    sem_hits: dict[uuid.UUID, MessageSearchHit] = {}
    for hit in sem_result.results:
        sem_scores[hit.message_id] = hit.rank
        sem_hits[hit.message_id] = hit

    # Combine all unique message IDs
    all_ids = set(fts_scores.keys()) | set(sem_scores.keys())

    # Calculate combined scores and build result list
    combined: list[tuple[float, MessageSearchHit]] = []
    for mid in all_ids:
        fts_rank = fts_scores.get(mid, 0.0)
        sem_rank = sem_scores.get(mid, 0.0)
        combined_score = _FTS_WEIGHT * fts_rank + _SEMANTIC_WEIGHT * sem_rank

        # Use FTS hit as the base result if available, otherwise semantic
        base_hit = fts_hits.get(mid) or sem_hits[mid]
        merged_hit = MessageSearchHit(
            message_id=base_hit.message_id,
            subject=base_hit.subject,
            sender_name=base_hit.sender_name,
            sender_email=base_hit.sender_email,
            gmail_date=base_hit.gmail_date,
            snippet=base_hit.snippet,
            group_id=base_hit.group_id,
            thread_id=base_hit.thread_id,
            rank=combined_score,
        )
        combined.append((combined_score, merged_hit))

    # Sort by combined score descending
    combined.sort(key=lambda x: x[0], reverse=True)

    total = len(combined)

    # Apply pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated = [hit for _, hit in combined[start:end]]

    return SearchResult(
        results=paginated,
        total=total,
        page=page,
        per_page=per_page,
    )
