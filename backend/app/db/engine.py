"""Async SQLAlchemy engine and session factory.

Provides:
- create_engine(): create an async engine from a database URL
- session_factory(): create an async sessionmaker bound to an engine
- get_session(): async generator yielding sessions for FastAPI dependency injection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Module-level session factory, set during app startup via init_db().
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection string
            (e.g. ``postgresql+asyncpg://user:pass@host/db``).

    Returns:
        An :class:`AsyncEngine` instance.
    """
    return _create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to *engine*.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        An :class:`async_sessionmaker` configured with ``expire_on_commit=False``.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    The session is closed after the request completes, even if an error occurs.

    Usage::

        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    if _session_factory is None:  # pragma: no cover
        raise RuntimeError("Database not initialized — call init_db() first")

    session = _session_factory()
    try:
        yield session
    finally:
        await session.close()
