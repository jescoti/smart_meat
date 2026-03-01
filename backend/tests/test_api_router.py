"""Tests for API router aggregation."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.router import api_router


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_router)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAPIRouter:
    """Tests for the API router."""

    def test_router_is_importable(self) -> None:
        """The api_router should be importable from app.api.router."""
        assert api_router is not None

    def test_router_has_no_prefix(self) -> None:
        """The router should have no prefix — sub-routers already include /api/."""
        assert api_router.prefix == ""

    async def test_health_endpoint_not_on_aggregation_router(self) -> None:
        """Health endpoint lives in main.py, not on the aggregation router."""
        own_routes = [r.path for r in api_router.routes if hasattr(r, "path")]
        assert "/health" not in own_routes
        assert "/api/health" not in own_routes

    async def test_auth_routes_registered(self, client: AsyncClient) -> None:
        """Auth sub-router routes should be accessible via the aggregation router."""
        resp = await client.get("/api/auth/login")
        # Should not be 404 — route exists (may return 200 or redirect)
        assert resp.status_code != 404

    async def test_no_double_api_prefix(self) -> None:
        """No route should have double /api/api/ prefix."""
        routes = [r.path for r in api_router.routes if hasattr(r, "path")]
        assert not any(r.startswith("/api/api/") for r in routes)
