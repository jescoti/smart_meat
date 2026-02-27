"""Tests for main FastAPI application — written FIRST (TDD Red phase)."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


# Environment variables required for settings to load
_ENV_VARS = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "test-secret-key",
    "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
}


@pytest.mark.asyncio
async def test_health_endpoint_returns_200() -> None:
    """GET /api/health must return HTTP 200."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_returns_correct_json() -> None:
    """GET /api/health must return {"status": "ok"}."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_endpoint_content_type_is_json() -> None:
    """GET /api/health must return application/json content type."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")

        assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_error_handler_returns_generic_error_format() -> None:
    """Unhandled exceptions must return generic error format without stack traces."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/trigger-error")

        assert response.status_code == 500
        body = response.json()
        # Must have error and message keys
        assert "error" in body
        assert "message" in body
        # Must have request_id as a uuid-like string
        assert "request_id" in body
        assert len(body["request_id"]) > 0
        # Must NOT expose stack traces or raw exception details
        assert "traceback" not in str(body).lower()
        assert "Traceback" not in str(body)


@pytest.mark.asyncio
async def test_error_handler_does_not_expose_stack_trace() -> None:
    """Error responses must never contain Python stack trace details."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/trigger-error")

        body_text = response.text
        # Stack trace indicators must not appear in response body
        assert "File " not in body_text
        assert "line " not in body_text


@pytest.mark.asyncio
async def test_404_unknown_route() -> None:
    """Unknown routes must return 404."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/nonexistent-route")

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown() -> None:
    """Lifespan context manager must run startup and shutdown without error.

    We call lifespan() directly so both the startup (before yield) and the
    shutdown (after yield) halves are executed, giving 100% branch coverage
    of the lifespan generator.
    """
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app, lifespan

        # Drive the full startup → yield → shutdown cycle directly.
        async with lifespan(app):
            pass  # startup done; now exit to trigger shutdown branch
