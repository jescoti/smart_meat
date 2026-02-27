"""Tests for JWT authentication middleware.

TDD RED phase — these tests are written before the implementation.
Uses httpx.AsyncClient with ASGITransport for integration-style testing.
"""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.auth import AuthMiddleware

SECRET_KEY = "test-secret-key"


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/login")
    async def login() -> dict[str, str]:
        return {"status": "login"}

    @app.get("/api/auth/callback")
    async def callback() -> dict[str, str]:
        return {"status": "callback"}

    @app.post("/api/auth/refresh")
    async def refresh() -> dict[str, str]:
        return {"status": "refresh"}

    @app.get("/api/protected")
    async def protected(request: Request) -> dict[str, str]:
        return {"user_id": request.state.user_id}

    @app.get("/non-api/page")
    async def non_api() -> dict[str, str]:
        return {"status": "public"}

    return app


@pytest.fixture
def app() -> FastAPI:
    return _create_test_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAuthMiddlewareSkipPaths:
    """Auth middleware should skip validation for certain paths."""

    async def test_health_endpoint_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_login_endpoint_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/login")
        assert resp.status_code == 200

    async def test_callback_endpoint_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/callback")
        assert resp.status_code == 200

    async def test_refresh_endpoint_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 200

    async def test_non_api_path_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/non-api/page")
        assert resp.status_code == 200


class TestAuthMiddlewareProtected:
    """Auth middleware should enforce JWT validation on protected endpoints."""

    async def test_missing_cookie_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/protected")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert "message" in body

    async def test_invalid_token_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/protected",
            cookies={"access_token": "invalid-jwt-token"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"

    async def test_expired_token_returns_401(self, client: AsyncClient) -> None:
        from app.auth.jwt import create_access_token

        expired_token = create_access_token("user-123", SECRET_KEY, ttl_minutes=0)
        resp = await client.get(
            "/api/protected",
            cookies={"access_token": expired_token},
        )
        assert resp.status_code == 401

    async def test_valid_token_sets_user_id_on_request_state(self, client: AsyncClient) -> None:
        from app.auth.jwt import create_access_token

        user_id = "550e8400-e29b-41d4-a716-446655440000"
        token = create_access_token(user_id, SECRET_KEY)
        resp = await client.get(
            "/api/protected",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == user_id

    async def test_wrong_secret_returns_401(self, client: AsyncClient) -> None:
        from app.auth.jwt import create_access_token

        # Token signed with a different secret
        token = create_access_token("user-123", "different-secret-key")
        resp = await client.get(
            "/api/protected",
            cookies={"access_token": token},
        )
        assert resp.status_code == 401

    async def test_401_response_is_json(self, client: AsyncClient) -> None:
        resp = await client.get("/api/protected")
        assert resp.headers["content-type"] == "application/json"

    async def test_empty_cookie_value_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/protected",
            cookies={"access_token": ""},
        )
        assert resp.status_code == 401
