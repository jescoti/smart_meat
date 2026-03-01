"""Tests for main FastAPI application — covers wiring, lifespan, and middleware."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


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
async def test_404_unknown_non_api_route() -> None:
    """Unknown non-API routes (which bypass auth) must return 404."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/nonexistent-route")

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_401_unknown_api_route_without_auth() -> None:
    """Unknown API routes without auth cookie must return 401 (auth blocks first)."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/nonexistent-route")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_lifespan_initializes_db_and_disposes() -> None:
    """Lifespan must call init_db on startup and dispose_db on shutdown."""
    with (
        patch.dict("os.environ", _ENV_VARS, clear=False),
        patch("app.main.init_db") as mock_init,
        patch("app.main.dispose_db", new_callable=AsyncMock) as mock_dispose,
    ):
        from app.main import app, lifespan

        async with lifespan(app):
            mock_init.assert_called_once_with(_ENV_VARS["DATABASE_URL"])

        mock_dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_router_routes_are_registered() -> None:
    """The api_router must be included — sub-router routes must be accessible."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        # Auth login is a public sub-router endpoint — must be present
        assert "/api/auth/login" in routes


@pytest.mark.asyncio
async def test_auth_login_no_double_prefix() -> None:
    """Auth routes must not have double /api/api/ prefix."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        routes = [r.path for r in app.routes if hasattr(r, "path")]
        # No route should start with /api/api/
        assert not any(r.startswith("/api/api/") for r in routes)


@pytest.mark.asyncio
async def test_auth_middleware_rejects_unauthenticated_protected_routes() -> None:
    """Protected routes must return 401 without auth cookie."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/consent")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_returns_401_without_cookie() -> None:
    """Dashboard summary must return 401 without auth cookie."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/dashboard/summary")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_cors_preflight_on_protected_endpoint() -> None:
    """CORS OPTIONS preflight on protected endpoints must return 200 with CORS headers."""
    with patch.dict("os.environ", {**_ENV_VARS, "CORS_ORIGINS": '["http://localhost:3000"]'}, clear=False):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/consent",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_session_dependency_overrides_are_set() -> None:
    """All 8 router session dependencies must be overridden."""
    with patch.dict("os.environ", _ENV_VARS, clear=False):
        from app.main import app

        # All 8 router modules + middleware consent module have session deps
        from app.api.auth import _get_session_dependency as auth_dep
        from app.api.consent import _get_session_dependency as consent_dep
        from app.api.dashboard import _get_session_dependency as dashboard_dep
        from app.api.groups import _get_session_dependency as groups_dep
        from app.api.knowledge import _get_session_dependency as knowledge_dep
        from app.api.messages import _get_session_dependency as messages_dep
        from app.api.reply import _get_session_dependency as reply_dep
        from app.api.search import _get_session_dependency as search_dep
        from app.middleware.consent import _get_session_dependency as consent_mw_dep

        deps = [
            auth_dep, consent_dep, dashboard_dep, groups_dep,
            knowledge_dep, messages_dep, reply_dep, search_dep,
            consent_mw_dep,
        ]

        for dep in deps:
            assert dep in app.dependency_overrides, (
                f"{dep.__module__}._get_session_dependency is not overridden"
            )
