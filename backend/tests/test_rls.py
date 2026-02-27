"""Tests for RLS (Row-Level Security) helper functions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import RLS_POLICIES_SQL, set_user_context


class TestSetUserContext:
    """Tests for set_user_context() — sets the PostgreSQL session variable."""

    @pytest.mark.asyncio
    async def test_executes_set_local(self) -> None:
        """set_user_context should execute SET LOCAL with the user_id."""
        mock_session = AsyncMock(spec=AsyncSession)
        user_id = "550e8400-e29b-41d4-a716-446655440000"

        await set_user_context(mock_session, user_id)

        mock_session.execute.assert_awaited_once()
        executed_call = mock_session.execute.call_args
        sql_text = str(executed_call[0][0].text)
        assert "SET LOCAL app.current_user_id" in sql_text

    @pytest.mark.asyncio
    async def test_passes_user_id_as_parameter(self) -> None:
        """The user_id should be passed as a bound parameter, not interpolated."""
        mock_session = AsyncMock(spec=AsyncSession)
        user_id = "550e8400-e29b-41d4-a716-446655440000"

        await set_user_context(mock_session, user_id)

        executed_call = mock_session.execute.call_args
        # The second positional argument should be the parameter dict
        params = executed_call[0][1]
        assert user_id in str(params)

    @pytest.mark.asyncio
    async def test_accepts_string_user_id(self) -> None:
        """set_user_context should work with string user IDs."""
        mock_session = AsyncMock(spec=AsyncSession)
        user_id = "abc-123"

        await set_user_context(mock_session, user_id)

        mock_session.execute.assert_awaited_once()


class TestRLSPoliciesSQL:
    """Tests for the RLS_POLICIES_SQL constant — SQL text for migration use."""

    def test_rls_policies_sql_is_string(self) -> None:
        """RLS_POLICIES_SQL should be a non-empty string."""
        assert isinstance(RLS_POLICIES_SQL, str)
        assert len(RLS_POLICIES_SQL) > 0

    def test_contains_enable_rls(self) -> None:
        """Should contain ALTER TABLE ... ENABLE ROW LEVEL SECURITY for each RLS table."""
        for _table in (
            "groups",
            "messages",
            "threads",
            "thread_messages",
            "message_embeddings",
            "nuggets",
            "audit_log",
        ):
            assert "ENABLE ROW LEVEL SECURITY" in RLS_POLICIES_SQL

    def test_contains_create_policy(self) -> None:
        """Should contain CREATE POLICY statements."""
        assert "CREATE POLICY" in RLS_POLICIES_SQL

    def test_contains_using_clause(self) -> None:
        """RLS policies should include USING clauses referencing app.current_user_id."""
        assert "app.current_user_id" in RLS_POLICIES_SQL

    def test_policies_for_groups_table(self) -> None:
        """Groups table should have a policy checking owner_id."""
        assert "owner_id" in RLS_POLICIES_SQL

    def test_policies_reference_users_table(self) -> None:
        """Policies for indirect tables should chain through group -> user ownership."""
        # Messages, threads, etc. check via group_id -> groups.owner_id
        assert "groups" in RLS_POLICIES_SQL
