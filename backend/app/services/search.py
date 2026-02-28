"""Full-text search service for messages.

Uses PostgreSQL ``websearch_to_tsquery`` for user-friendly query parsing and
``ts_rank_cd`` for relevance scoring.  All queries are parameterised — user
input is never interpolated into SQL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, Message, ThreadMessage


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
    ts_vector = func.to_tsvector(
        "english", func.coalesce(Message.body_text, "")
    )

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
