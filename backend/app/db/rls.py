"""Row-Level Security (RLS) helpers.

Provides:
- set_user_context(): sets the PostgreSQL session variable for RLS policies
- RLS_POLICIES_SQL: SQL text for creating RLS policies (used in Alembic migrations)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def set_user_context(session: AsyncSession, user_id: str) -> None:
    """Set the current user context for PostgreSQL RLS policies.

    Executes ``SET LOCAL app.current_user_id = :user_id`` so that
    RLS policies can filter rows based on the authenticated user.

    This must be called within an active transaction — ``SET LOCAL``
    reverts when the transaction ends.

    Args:
        session: An active async database session.
        user_id: The UUID string of the authenticated user.
    """
    await session.execute(
        text("SET LOCAL app.current_user_id = :user_id"),
        {"user_id": user_id},
    )


# ---------------------------------------------------------------------------
# RLS policy definitions (for use in Alembic migrations)
# ---------------------------------------------------------------------------

RLS_POLICIES_SQL = """
-- Enable RLS on all user-scoped tables
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE thread_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE nuggets ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Groups: owner can see their own groups
CREATE POLICY groups_user_isolation ON groups
    USING (owner_id = current_setting('app.current_user_id')::uuid);

-- Messages: user can see messages in their groups
CREATE POLICY messages_user_isolation ON messages
    USING (group_id IN (
        SELECT id FROM groups WHERE owner_id = current_setting('app.current_user_id')::uuid
    ));

-- Threads: user can see threads in their groups
CREATE POLICY threads_user_isolation ON threads
    USING (group_id IN (
        SELECT id FROM groups WHERE owner_id = current_setting('app.current_user_id')::uuid
    ));

-- ThreadMessages: user can see thread_messages for threads in their groups
CREATE POLICY thread_messages_user_isolation ON thread_messages
    USING (thread_id IN (
        SELECT t.id FROM threads t
        JOIN groups g ON t.group_id = g.id
        WHERE g.owner_id = current_setting('app.current_user_id')::uuid
    ));

-- MessageEmbeddings: user can see embeddings for messages in their groups
CREATE POLICY message_embeddings_user_isolation ON message_embeddings
    USING (message_id IN (
        SELECT m.id FROM messages m
        JOIN groups g ON m.group_id = g.id
        WHERE g.owner_id = current_setting('app.current_user_id')::uuid
    ));

-- Nuggets: user can see nuggets in their groups
CREATE POLICY nuggets_user_isolation ON nuggets
    USING (group_id IN (
        SELECT id FROM groups WHERE owner_id = current_setting('app.current_user_id')::uuid
    ));

-- AuditLog: user can see their own audit entries
CREATE POLICY audit_log_user_isolation ON audit_log
    USING (user_id = current_setting('app.current_user_id')::uuid);
""".strip()
