"""JWZ threading engine for email message threading.

Implements the Jamie Zawinski (JWZ) threading algorithm adapted for
mailing list archives. The algorithm reconstructs conversation threads
from email headers (Message-ID, In-Reply-To, References).

Algorithm phases:
    1. Build ID Table — create Container objects keyed by Message-ID
    2. Build References — link containers via References + In-Reply-To headers
    3. Find Root Set — collect containers with no parent
    4. Prune Empty — remove/promote ghost containers
    5. Group by Subject — merge roots with matching normalized subjects

Public API:
    thread_messages(group_id, session) — full pipeline with DB persistence
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models import (
    Message,
    MessageProcessingStatus,
    Thread,
    ThreadMessage,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Fallback datetime for sorting containers without dates
_NOW_FALLBACK = datetime(2000, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Container dataclass — internal node for the threading tree
# ---------------------------------------------------------------------------

_SUBJECT_PREFIX_RE = re.compile(
    r"^(\s*"
    r"(?:"
    r"(?:re|fwd?)\s*:\s*"  # Re: / Fwd: / Fw:
    r"|"
    r"\[[^\]]*\]\s*"  # [tag]
    r")"
    r")+",
    re.IGNORECASE,
)


@dataclass
class Container:
    """Node in the threading tree. Wraps an optional Message."""

    message_id: str
    message: Message | None = None
    parent: Container | None = field(default=None, repr=False)
    children: list[Container] = field(default_factory=list)
    is_ghost: bool = True  # True when no real message is attached

    def __post_init__(self) -> None:
        if self.message is not None:
            self.is_ghost = False


# ---------------------------------------------------------------------------
# normalize_subject()
# ---------------------------------------------------------------------------


def normalize_subject(subject: str) -> str:
    """Strip Re:, Fwd:, [tags], and whitespace; lowercase the result.

    Examples:
        >>> normalize_subject("Re: [dev-list] Hello World")
        'hello world'
        >>> normalize_subject("  Fwd: Re: [urgent] Topic  ")
        'topic'
    """
    stripped = _SUBJECT_PREFIX_RE.sub("", subject)
    return stripped.strip().lower()


# ---------------------------------------------------------------------------
# Phase 1: Build ID Table
# ---------------------------------------------------------------------------


def _build_id_table(messages: list[Message]) -> dict[str, Container]:
    """Create a Container for each message, keyed by ``message_id_header``.

    Also pre-creates ghost containers for all IDs mentioned in References
    and In-Reply-To headers. This means that when a real message appears
    later in the list whose Message-ID matches a previously-created ghost,
    the ghost is filled with the real message.

    Duplicate message IDs are silently ignored (first one wins).
    """
    table: dict[str, Container] = {}

    # First pass: create ghost containers for all referenced IDs
    for msg in messages:
        if msg.references_header:
            for ref_id in msg.references_header:
                if ref_id not in table:
                    table[ref_id] = Container(message_id=ref_id)
        if msg.in_reply_to and msg.in_reply_to not in table:
            table[msg.in_reply_to] = Container(message_id=msg.in_reply_to)

    # Second pass: create or fill containers for each message
    for msg in messages:
        mid = msg.message_id_header
        if mid in table:
            existing = table[mid]
            # Only fill a ghost container; skip true duplicates
            if existing.message is None:
                existing.message = msg
                existing.is_ghost = False
            # else: duplicate Message-ID — keep the first one
        else:
            table[mid] = Container(message_id=mid, message=msg)

    return table


# ---------------------------------------------------------------------------
# Phase 2: Build References Graph
# ---------------------------------------------------------------------------


def _has_ancestor(container: Container, candidate: Container) -> bool:
    """Check if *candidate* is an ancestor of *container* (cycle detection)."""
    node = container.parent
    while node is not None:
        if node is candidate:
            return True
        node = node.parent
    return False


def _set_parent(child: Container, parent: Container) -> None:
    """Set *parent* as parent of *child*, with cycle detection.

    If the link would create a cycle, the operation is a no-op.
    Also removes *child* from its old parent's children list.
    """
    if child is parent:
        return
    # Cycle check: walk parent's ancestors to see if child is already there
    if _has_ancestor(parent, child):
        return
    # Remove from old parent
    if child.parent is not None:
        child.parent.children = [c for c in child.parent.children if c is not child]
    child.parent = parent
    if child not in parent.children:
        parent.children.append(child)


def _build_references(containers: dict[str, Container], messages: list[Message]) -> None:
    """Link containers based on References + In-Reply-To headers.

    For each message:
    1. Build a reference list from ``references_header``.
    2. Append ``in_reply_to`` if not already the last element.
    3. Walk consecutive pairs, setting parent→child links.
    4. Set the last reference as parent of the current message's container.
    """
    for msg in messages:
        refs: list[str] = list(msg.references_header) if msg.references_header else []

        # Append In-Reply-To if present and not already the last ref
        if msg.in_reply_to:
            if not refs or refs[-1] != msg.in_reply_to:
                refs.append(msg.in_reply_to)

        if not refs:
            continue

        # Ensure all referenced IDs have containers (ghosts if unknown)
        for ref_id in refs:
            if ref_id not in containers:
                containers[ref_id] = Container(message_id=ref_id)

        # Link consecutive pairs
        for i in range(len(refs) - 1):
            parent_c = containers[refs[i]]
            child_c = containers[refs[i + 1]]
            # Only set parent if child doesn't already have one
            if child_c.parent is None:
                _set_parent(child_c, parent_c)

        # Link last reference as parent of this message's container
        msg_container = containers[msg.message_id_header]
        last_ref_container = containers[refs[-1]]
        if msg_container is not last_ref_container:
            _set_parent(msg_container, last_ref_container)


# ---------------------------------------------------------------------------
# Phase 3: Find Root Set
# ---------------------------------------------------------------------------


def _find_root_set(containers: dict[str, Container]) -> list[Container]:
    """Collect all containers that have no parent."""
    return [c for c in containers.values() if c.parent is None]


# ---------------------------------------------------------------------------
# Phase 4: Prune Empty Containers
# ---------------------------------------------------------------------------


def _prune_children(container: Container) -> None:
    """Recursively prune ghost containers from children."""
    i = 0
    while i < len(container.children):
        child = container.children[i]
        # Recurse first
        _prune_children(child)

        if child.message is None and child.is_ghost:
            if len(child.children) == 0:
                # Ghost with no children — remove
                container.children.pop(i)
                continue
            elif len(child.children) == 1:
                # Ghost with one child — promote child
                grandchild = child.children[0]
                grandchild.parent = container
                container.children[i] = grandchild
                # Don't increment i — re-check the promoted child
                continue
            # Ghost with multiple children — keep it
        i += 1


def _prune_empty(roots: list[Container]) -> list[Container]:
    """Remove or promote ghost containers from the root set.

    Rules:
    - Ghost with no children → remove entirely
    - Ghost with one child → replace with the child
    - Ghost with multiple children → keep (structural node)
    - Non-ghost roots are always kept

    Also recurses into children of each root.
    """
    result: list[Container] = []

    for root in roots:
        # First, prune within the tree
        _prune_children(root)

        if root.message is not None or not root.is_ghost:
            result.append(root)
        elif len(root.children) == 0:
            # Ghost root with no children — discard
            continue
        elif len(root.children) == 1:
            # Ghost root with one child — promote child to root
            child = root.children[0]
            child.parent = None
            result.append(child)
        else:
            # Ghost root with multiple children — keep as structural node
            result.append(root)

    return result


# ---------------------------------------------------------------------------
# Phase 5: Subject-Based Grouping (Fallback)
# ---------------------------------------------------------------------------


def _earliest_date(container: Container) -> datetime | None:
    """Find the earliest message date in a container tree."""
    dates: list[datetime] = []
    stack = [container]
    while stack:
        node = stack.pop()
        if node.message is not None:
            dates.append(node.message.date)
        stack.extend(node.children)
    return min(dates) if dates else None


def _container_subject(container: Container) -> str:
    """Get subject from a container (or its first non-ghost descendant)."""
    if container.message is not None:
        return container.message.subject
    # Search children for a message
    stack = list(container.children)
    while stack:
        node = stack.pop()
        if node.message is not None:
            return node.message.subject
        stack.extend(node.children)
    return ""


def _group_by_subject(roots: list[Container], time_window_hours: int = 72) -> list[Container]:
    """Merge roots with the same normalized subject within a time window.

    Args:
        roots: List of root containers.
        time_window_hours: Maximum hours between earliest messages for merging.

    Returns:
        Merged list of root containers.
    """
    if len(roots) <= 1:
        return roots

    window = timedelta(hours=time_window_hours)

    # Group by normalized subject
    subject_groups: dict[str, list[Container]] = {}
    no_subject: list[Container] = []

    for root in roots:
        subj = normalize_subject(_container_subject(root))
        if not subj:
            no_subject.append(root)
        else:
            subject_groups.setdefault(subj, []).append(root)

    result: list[Container] = list(no_subject)

    for _subj, group in subject_groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Sort by earliest date so we merge into the oldest
        group.sort(key=lambda c: _earliest_date(c) or _NOW_FALLBACK)

        merged: list[Container] = [group[0]]
        for candidate in group[1:]:
            # Try to merge with the first root in merged list
            base = merged[0]
            base_date = _earliest_date(base)
            cand_date = _earliest_date(candidate)

            if base_date is not None and cand_date is not None:
                if abs(cand_date - base_date) <= window:
                    # Merge: prefer real message root over ghost
                    if base.is_ghost and not candidate.is_ghost:
                        # Swap: make candidate the new base
                        candidate.children.extend(base.children)
                        for child in base.children:
                            child.parent = candidate
                        if base.children:
                            base.children = []
                        # Also add base's ghost children if it's structural
                        merged[0] = candidate
                    else:
                        # Add candidate as child of base
                        _set_parent(candidate, base)
                    continue

            merged.append(candidate)

        result.extend(merged)

    return result


# ---------------------------------------------------------------------------
# Tree traversal helpers
# ---------------------------------------------------------------------------


def _collect_messages(container: Container) -> list[tuple[Container, int]]:
    """Depth-first traversal collecting (container, depth) pairs."""
    result: list[tuple[Container, int]] = []
    stack: list[tuple[Container, int]] = [(container, 0)]
    while stack:
        node, depth = stack.pop()
        result.append((node, depth))
        # Push children in reverse so leftmost child is visited first
        for child in reversed(node.children):
            stack.append((child, depth + 1))
    return result


# ---------------------------------------------------------------------------
# Main entry point: thread_messages()
# ---------------------------------------------------------------------------


async def thread_messages(group_id: uuid.UUID, session: AsyncSession) -> list[Thread]:
    """Run the JWZ threading algorithm and persist results.

    Args:
        group_id: The group whose messages to thread.
        session: SQLAlchemy async session for DB operations.

    Returns:
        List of Thread ORM objects created/updated.
    """
    # Load pending messages for this group
    stmt = select(Message).where(
        Message.group_id == group_id,
        Message.processing_status == MessageProcessingStatus.pending,
    )
    result = await session.execute(stmt)
    messages: list[Message] = list(result.scalars().all())

    if not messages:
        return []

    # Run the JWZ algorithm
    containers = _build_id_table(messages)
    _build_references(containers, messages)
    roots = _find_root_set(containers)
    roots = _prune_empty(roots)
    roots = _group_by_subject(roots)

    # Persist results
    created_threads: list[Thread] = []

    for root in roots:
        # Collect all nodes in this thread tree
        node_list = _collect_messages(root)

        # Compute thread metadata
        real_messages: list[Message] = []
        sender_emails: set[str] = set()
        all_dates: list[datetime] = []

        for node, _depth in node_list:
            if node.message is not None:
                real_messages.append(node.message)
                sender_emails.add(node.message.sender_email)
                all_dates.append(node.message.date)

        # Determine thread subject
        subject = _container_subject(root)

        # Create Thread record
        thread = Thread()
        thread.id = uuid.uuid4()
        thread.group_id = group_id
        thread.subject = subject
        thread.message_count = len(real_messages)
        thread.participant_count = len(sender_emails)
        thread.last_message_at = max(all_dates) if all_dates else None

        session.add(thread)

        # Create ThreadMessage records
        thread_message_records: list[ThreadMessage] = []
        # Map message_id_header -> Message.id for parent lookups
        mid_to_db_id: dict[str, uuid.UUID] = {}
        # Ghost containers need synthetic UUIDs for their DB records
        ghost_db_ids: dict[str, uuid.UUID] = {}

        for node, _depth in node_list:
            if node.message is not None:
                mid_to_db_id[node.message_id] = node.message.id

        for position, (node, depth) in enumerate(node_list):
            tm = ThreadMessage()
            tm.id = uuid.uuid4()
            tm.thread_id = thread.id
            tm.position = position
            tm.depth = depth
            tm.is_ghost = node.is_ghost

            if node.message is not None:
                tm.message_id = node.message.id
                mid_to_db_id[node.message_id] = node.message.id
            else:
                # Ghost node — needs a synthetic message_id
                # We use a deterministic UUID based on the ghost's message_id string
                ghost_id = ghost_db_ids.get(node.message_id)
                if ghost_id is None:
                    ghost_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ghost:{node.message_id}")
                    ghost_db_ids[node.message_id] = ghost_id
                tm.message_id = ghost_id
                mid_to_db_id[node.message_id] = ghost_id

            # Set parent_message_id
            if node.parent is not None:
                parent_db_id = mid_to_db_id.get(node.parent.message_id)
                tm.parent_message_id = parent_db_id
            else:
                tm.parent_message_id = None

            thread_message_records.append(tm)

        session.add_all(thread_message_records)
        created_threads.append(thread)

    # Update processing status
    for msg in messages:
        msg.processing_status = MessageProcessingStatus.threaded

    await session.flush()

    return created_threads
