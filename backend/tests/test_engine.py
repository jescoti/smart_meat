"""Tests for async SQLAlchemy engine and session factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.engine import create_engine, get_session, session_factory

# ---------------------------------------------------------------------------
# Engine creation
# ---------------------------------------------------------------------------


class TestCreateEngine:
    """Tests for the create_engine() function."""

    @patch("app.db.engine._create_async_engine")
    def test_creates_engine_with_database_url(self, mock_create: MagicMock) -> None:
        """create_engine passes DATABASE_URL from settings."""
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create.return_value = mock_engine

        create_engine("postgresql+asyncpg://localhost/test")

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[0][0] == "postgresql+asyncpg://localhost/test"

    @patch("app.db.engine._create_async_engine")
    def test_engine_echo_defaults_false(self, mock_create: MagicMock) -> None:
        """Engine echo should default to False."""
        mock_create.return_value = MagicMock(spec=AsyncEngine)

        create_engine("postgresql+asyncpg://localhost/test")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs.get("echo") is False

    @patch("app.db.engine._create_async_engine")
    def test_engine_pool_pre_ping_enabled(self, mock_create: MagicMock) -> None:
        """Engine should enable pool_pre_ping for connection health checks."""
        mock_create.return_value = MagicMock(spec=AsyncEngine)

        create_engine("postgresql+asyncpg://localhost/test")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs.get("pool_pre_ping") is True

    @patch("app.db.engine._create_async_engine")
    def test_returns_async_engine(self, mock_create: MagicMock) -> None:
        """create_engine should return whatever the underlying factory returns."""
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_create.return_value = mock_engine

        result = create_engine("postgresql+asyncpg://localhost/test")

        assert result is mock_engine


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------


class TestSessionFactory:
    """Tests for the session_factory() function."""

    def test_returns_async_sessionmaker(self) -> None:
        """session_factory should return an async_sessionmaker bound to the engine."""
        mock_engine = MagicMock(spec=AsyncEngine)

        factory = session_factory(mock_engine)

        assert isinstance(factory, async_sessionmaker)

    def test_session_expire_on_commit_false(self) -> None:
        """Sessions should not expire on commit for better async ergonomics."""
        mock_engine = MagicMock(spec=AsyncEngine)

        factory = session_factory(mock_engine)

        # async_sessionmaker stores kw in its internal dict
        assert factory.kw.get("expire_on_commit") is False


# ---------------------------------------------------------------------------
# get_session dependency
# ---------------------------------------------------------------------------


class TestGetSession:
    """Tests for the get_session() async generator."""

    @pytest.mark.asyncio
    async def test_yields_session(self) -> None:
        """get_session should yield an AsyncSession."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.db.engine._session_factory", mock_factory):
            sessions = []
            async for session in get_session():
                sessions.append(session)

            assert len(sessions) == 1
            assert sessions[0] is mock_session

    @pytest.mark.asyncio
    async def test_closes_session_after_yield(self) -> None:
        """get_session should close the session after the generator exits."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.db.engine._session_factory", mock_factory):
            async for _session in get_session():
                pass  # consume the generator

            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self) -> None:
        """get_session should close the session even if the consumer raises."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.db.engine._session_factory", mock_factory):
            gen = get_session()
            session = await gen.__anext__()
            assert session is mock_session

            # Throw an exception into the generator, which should trigger finally
            with pytest.raises(RuntimeError, match="test error"):
                await gen.athrow(RuntimeError("test error"))

            mock_session.close.assert_awaited_once()
