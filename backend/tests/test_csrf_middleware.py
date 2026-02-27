"""Tests for CSRF double-submit cookie middleware.

TDD RED phase — these tests are written before the implementation.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.csrf import CSRFMiddleware


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with CSRF middleware for testing."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

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

    @app.get("/api/data")
    async def get_data() -> dict[str, str]:
        return {"data": "safe-method"}

    @app.post("/api/data")
    async def post_data() -> dict[str, str]:
        return {"data": "created"}

    @app.put("/api/data")
    async def put_data() -> dict[str, str]:
        return {"data": "updated"}

    @app.delete("/api/data")
    async def delete_data() -> dict[str, str]:
        return {"data": "deleted"}

    @app.patch("/api/data")
    async def patch_data() -> dict[str, str]:
        return {"data": "patched"}

    @app.post("/non-api/submit")
    async def non_api_submit() -> dict[str, str]:
        return {"status": "submitted"}

    return app


@pytest.fixture
def app() -> FastAPI:
    return _create_test_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestCSRFSafeMethodsSkipped:
    """CSRF validation should be skipped for safe HTTP methods."""

    async def test_get_request_passes(self, client: AsyncClient) -> None:
        resp = await client.get("/api/data")
        assert resp.status_code == 200

    async def test_head_request_passes(self, client: AsyncClient) -> None:
        resp = await client.head("/api/data")
        # HEAD returns 200 or 405 depending on route, but not 403
        assert resp.status_code != 403

    async def test_options_request_passes(self, client: AsyncClient) -> None:
        resp = await client.options("/api/data")
        assert resp.status_code != 403


class TestCSRFSkipPaths:
    """CSRF validation should be skipped for exempt paths."""

    async def test_health_endpoint_skipped(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_login_endpoint_skipped(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/login")
        assert resp.status_code == 200

    async def test_callback_endpoint_skipped(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/callback")
        assert resp.status_code == 200

    async def test_refresh_endpoint_skipped(self, client: AsyncClient) -> None:
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 200

    async def test_non_api_path_skipped(self, client: AsyncClient) -> None:
        resp = await client.post("/non-api/submit")
        assert resp.status_code == 200


class TestCSRFMutatingMethods:
    """CSRF validation should enforce double-submit cookie on mutating methods."""

    async def test_post_without_csrf_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post("/api/data")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"] == "csrf_validation_failed"
        assert "message" in body

    async def test_put_without_csrf_returns_403(self, client: AsyncClient) -> None:
        resp = await client.put("/api/data")
        assert resp.status_code == 403

    async def test_delete_without_csrf_returns_403(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/data")
        assert resp.status_code == 403

    async def test_patch_without_csrf_returns_403(self, client: AsyncClient) -> None:
        resp = await client.patch("/api/data")
        assert resp.status_code == 403

    async def test_mismatched_tokens_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/data",
            cookies={"csrf_token": "token-a"},
            headers={"X-CSRF-Token": "token-b"},
        )
        assert resp.status_code == 403

    async def test_missing_header_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/data",
            cookies={"csrf_token": "valid-token"},
        )
        assert resp.status_code == 403

    async def test_missing_cookie_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/data",
            headers={"X-CSRF-Token": "valid-token"},
        )
        assert resp.status_code == 403

    async def test_matching_tokens_passes(self, client: AsyncClient) -> None:
        csrf_token = "my-csrf-token-value"
        resp = await client.post(
            "/api/data",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200

    async def test_matching_tokens_put(self, client: AsyncClient) -> None:
        csrf_token = "my-csrf-token-value"
        resp = await client.put(
            "/api/data",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200

    async def test_matching_tokens_delete(self, client: AsyncClient) -> None:
        csrf_token = "my-csrf-token-value"
        resp = await client.delete(
            "/api/data",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200

    async def test_matching_tokens_patch(self, client: AsyncClient) -> None:
        csrf_token = "my-csrf-token-value"
        resp = await client.patch(
            "/api/data",
            cookies={"csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200

    async def test_403_response_is_json(self, client: AsyncClient) -> None:
        resp = await client.post("/api/data")
        assert resp.headers["content-type"] == "application/json"

    async def test_empty_cookie_value_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/data",
            cookies={"csrf_token": ""},
            headers={"X-CSRF-Token": ""},
        )
        assert resp.status_code == 403

    async def test_empty_header_with_valid_cookie_returns_403(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/data",
            cookies={"csrf_token": "valid-token"},
            headers={"X-CSRF-Token": ""},
        )
        assert resp.status_code == 403


class TestCSRFTokenGeneration:
    """Test the generate_csrf_token utility."""

    def test_generate_csrf_token_returns_string(self) -> None:
        from app.middleware.csrf import generate_csrf_token

        token = generate_csrf_token()
        assert isinstance(token, str)

    def test_generate_csrf_token_is_non_empty(self) -> None:
        from app.middleware.csrf import generate_csrf_token

        token = generate_csrf_token()
        assert len(token) > 0

    def test_generate_csrf_token_is_unique(self) -> None:
        from app.middleware.csrf import generate_csrf_token

        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert token1 != token2
