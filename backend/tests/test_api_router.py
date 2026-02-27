"""Tests for API router aggregation.

TDD RED phase — these tests are written before the implementation.
"""

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

    def test_router_has_api_prefix(self) -> None:
        """The router should be configured with /api prefix."""
        assert api_router.prefix == "/api"

    async def test_health_endpoint(self, client: AsyncClient) -> None:
        """The router should include a health endpoint."""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
