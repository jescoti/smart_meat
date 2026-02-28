"""Knowledge service — CRUD for nuggets and LLM-powered extraction.

Provides functions for:
- Manual nugget creation
- Nugget listing with filters and pagination
- Nugget retrieval
- Accepting/rejecting suggestions
- Processing threads for nugget extraction via LLM
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import (
    AuditLog,
    Nugget,
    NuggetSourceType,
    NuggetStatus,
    Thread,
    ThreadMessage,
)
from app.services.llm import extract_nuggets


async def create_manual_nugget(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
    title: str,
    content: str,
    tags: list[str],
) -> Nugget:
    """Create a manually authored knowledge nugget.

    Manual nuggets are immediately accepted (not suggestions).
    """
    nugget = Nugget(
        group_id=group_id,
        source_message_id=source_message_id,
        title=title,
        content=content,
        tags=tags,
        source_type=NuggetSourceType.manual,
        status=NuggetStatus.accepted,
        created_by=user_id,
    )
    session.add(nugget)

    audit_entry = AuditLog(
        user_id=user_id,
        action="nugget_created",
        resource_type="nugget",
        resource_id=str(nugget.id),
    )
    session.add(audit_entry)

    await session.flush()
    return nugget


async def list_nuggets(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    status: NuggetStatus | None,
    page: int,
    per_page: int,
) -> tuple[list[Nugget], int]:
    """List nuggets for a group with optional status filter and pagination."""
    # Build base filter
    conditions = [Nugget.group_id == group_id, Nugget.created_by == user_id]
    if status is not None:
        conditions.append(Nugget.status == status)

    # Count total
    count_query = select(func.count(Nugget.id)).where(*conditions)
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    # Fetch paginated
    offset = (page - 1) * per_page
    nuggets_query = (
        select(Nugget)
        .where(*conditions)
        .order_by(Nugget.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    nuggets_result = await session.execute(nuggets_query)
    nuggets = list(nuggets_result.scalars().all())

    return nuggets, total


async def get_nugget(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    nugget_id: uuid.UUID,
) -> Nugget | None:
    """Get a single nugget by ID, scoped to the user."""
    query = select(Nugget).where(Nugget.id == nugget_id, Nugget.created_by == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def accept_suggestion(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    nugget_id: uuid.UUID,
) -> Nugget | None:
    """Accept a suggested nugget, changing its status to accepted."""
    nugget = await get_nugget(session=session, user_id=user_id, nugget_id=nugget_id)
    if nugget is None:
        return None

    nugget.status = NuggetStatus.accepted

    audit_entry = AuditLog(
        user_id=user_id,
        action="nugget_accepted",
        resource_type="nugget",
        resource_id=str(nugget_id),
    )
    session.add(audit_entry)

    await session.flush()
    return nugget


async def reject_suggestion(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    nugget_id: uuid.UUID,
) -> Nugget | None:
    """Reject a suggested nugget, changing its status to rejected."""
    nugget = await get_nugget(session=session, user_id=user_id, nugget_id=nugget_id)
    if nugget is None:
        return None

    nugget.status = NuggetStatus.rejected

    audit_entry = AuditLog(
        user_id=user_id,
        action="nugget_rejected",
        resource_type="nugget",
        resource_id=str(nugget_id),
    )
    session.add(audit_entry)

    await session.flush()
    return nugget


async def process_thread_for_nuggets(
    *,
    session: AsyncSession,
    thread_id: uuid.UUID,
    user_id: uuid.UUID,
    model: str,
    api_key: str,
) -> list[Nugget]:
    """Extract nuggets from a thread using the LLM.

    Guards:
    - Thread must exist.
    - Thread must have between 2 and 20 messages (inclusive).

    Creates nuggets with status=suggested and source_type=llm_extracted.
    """
    # Load thread
    thread_result = await session.execute(
        select(Thread).where(Thread.id == thread_id)
    )
    thread = thread_result.scalar_one_or_none()

    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")

    if thread.message_count < 2 or thread.message_count > 20:
        raise ValueError(
            f"Thread must have between 2 and 20 messages, got {thread.message_count}"
        )

    # Load messages
    tms_result = await session.execute(
        select(ThreadMessage)
        .where(ThreadMessage.thread_id == thread_id)
        .options(joinedload(ThreadMessage.message))
    )
    thread_messages = tms_result.scalars().all()

    # Format messages for LLM
    messages_for_llm = [
        {
            "sender_name": tm.message.sender_name or "Unknown",
            "body_text": tm.message.body_text or "",
            "gmail_date": tm.message.date.isoformat() if tm.message.date else "",
        }
        for tm in thread_messages
    ]

    # Extract nuggets via LLM
    extracted = await extract_nuggets(messages_for_llm, model, api_key)

    # Create nugget records
    nuggets: list[Nugget] = []
    for item in extracted:
        nugget = Nugget(
            group_id=thread.group_id,
            title=item["title"],
            content=item["content"],
            tags=item.get("tags", []),
            source_type=NuggetSourceType.llm_extracted,
            status=NuggetStatus.suggested,
            created_by=user_id,
        )
        session.add(nugget)
        nuggets.append(nugget)

        audit_entry = AuditLog(
            user_id=user_id,
            action="nugget_extracted",
            resource_type="nugget",
            resource_id=str(nugget.id),
        )
        session.add(audit_entry)

    await session.flush()
    return nuggets
