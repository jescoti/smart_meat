"""Async SQLAlchemy engine and session factory.

Provides:
- create_engine(): create an async engine from a database URL
- session_factory(): create an async sessionmaker bound to an engine
- init_db(): initialize engine + session factory (called at app startup)
- dispose_db(): dispose engine and clear state (called at app shutdown)
- get_session(): async generator yielding sessions for FastAPI dependency injection
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
)

# Query parameters that asyncpg does not understand (they belong to
# psycopg2 / libpq).  We silently strip them so the same DATABASE_URL
# works with both drivers.
_STRIP_PARAMS = frozenset({"sslmode"})

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Module-level state, set during app startup via init_db().
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _sanitize_url(database_url: str) -> str:
    """Strip query parameters that asyncpg does not support.

    asyncpg uses its own ``ssl`` keyword argument and does not understand
    the ``sslmode`` parameter used by psycopg2 / libpq.  This function
    removes those incompatible parameters so the same DATABASE_URL works
    regardless of driver.
    """
    parsed = urlparse(database_url)
    if not parsed.query:
        return database_url
    params = parse_qs(parsed.query)
    filtered = {k: v for k, v in params.items() if k not in _STRIP_PARAMS}
    new_query = urlencode(filtered, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection string
            (e.g. ``postgresql+asyncpg://user:pass@host/db``).

    Returns:
        An :class:`AsyncEngine` instance.
    """
    return _create_async_engine(
        _sanitize_url(database_url),
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


def init_db(database_url: str) -> None:
    """Initialize the database engine and session factory.

    Called once during app startup in the lifespan context manager.
    """
    global _engine, _session_factory
    _engine = create_engine(database_url)
    _session_factory = session_factory(_engine)


async def dispose_db() -> None:
    """Dispose the database engine and clear module-level state.

    Called once during app shutdown in the lifespan context manager.
    Safe to call even if init_db() was never called.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


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
