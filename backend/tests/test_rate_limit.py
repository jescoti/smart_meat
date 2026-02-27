"""Tests for Redis-backed rate limiter middleware.

TDD RED phase — these tests are written before the implementation.
Redis is mocked — no running Redis instance required.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.rate_limit import RateLimitConfig, RateLimitMiddleware


def _create_test_app(
    mock_redis: AsyncMock,
    config: RateLimitConfig | None = None,
) -> FastAPI:
    """Create a minimal FastAPI app with rate limit middleware for testing."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=mock_redis,
        config=config or RateLimitConfig(),
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/data")
    async def get_data(request: Request) -> dict[str, str]:
        return {"data": "ok"}

    @app.post("/api/auth/login")
    async def login() -> dict[str, str]:  # pragma: no cover
        return {"status": "login"}

    @app.post("/api/data")
    async def post_data() -> dict[str, str]:  # pragma: no cover
        return {"data": "created"}

    return app


def _create_mock_redis(current_count: int = 0) -> AsyncMock:
    """Create a mock Redis client.

    Args:
        current_count: The simulated current request count.
            If >= the rate limit, requests will be rate-limited.
    """
    mock = AsyncMock()

    # pipeline() returns a context manager that yields itself
    pipe = AsyncMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[current_count + 1, True])

    mock.pipeline = MagicMock(return_value=pipe)

    # TTL for retry-after calculation
    mock.ttl = AsyncMock(return_value=42)

    return mock


@pytest.fixture
def mock_redis() -> AsyncMock:
    return _create_mock_redis(current_count=0)


@pytest.fixture
async def client(mock_redis: AsyncMock) -> AsyncClient:
    app = _create_test_app(mock_redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRateLimitConfig:
    """Tests for RateLimitConfig defaults and customization."""

    def test_default_limit(self) -> None:
        config = RateLimitConfig()
        assert config.default_rpm == 100

    def test_default_auth_limit(self) -> None:
        config = RateLimitConfig()
        assert config.auth_rpm == 10

    def test_default_reply_limit(self) -> None:
        config = RateLimitConfig()
        assert config.reply_rpm == 10

    def test_default_llm_limit(self) -> None:
        config = RateLimitConfig()
        assert config.llm_rpm == 20

    def test_custom_config(self) -> None:
        config = RateLimitConfig(default_rpm=50, auth_rpm=5)
        assert config.default_rpm == 50
        assert config.auth_rpm == 5

    def test_window_seconds(self) -> None:
        config = RateLimitConfig()
        assert config.window_seconds == 60


class TestRateLimitMiddlewareUnderLimit:
    """Tests when requests are under the rate limit."""

    async def test_request_passes(self, client: AsyncClient) -> None:
        resp = await client.get("/api/data")
        assert resp.status_code == 200

    async def test_health_endpoint_passes(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200


class TestRateLimitMiddlewareOverLimit:
    """Tests when requests exceed the rate limit."""

    async def test_returns_429_when_over_limit(self) -> None:
        mock_redis = _create_mock_redis(current_count=100)
        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.status_code == 429

    async def test_429_response_has_retry_after_header(self) -> None:
        mock_redis = _create_mock_redis(current_count=100)
        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert "retry-after" in resp.headers

    async def test_429_response_body(self) -> None:
        mock_redis = _create_mock_redis(current_count=100)
        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            body = resp.json()
            assert body["error"] == "rate_limited"
            assert "message" in body
            assert "retry_after" in body

    async def test_429_response_is_json(self) -> None:
        mock_redis = _create_mock_redis(current_count=100)
        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.headers["content-type"] == "application/json"


class TestRateLimitKeyStrategy:
    """Tests for per-user and per-IP rate limit keys."""

    async def test_uses_user_id_when_available(self) -> None:
        """When request.state.user_id is set, rate limit key uses user_id."""
        mock_redis = _create_mock_redis(current_count=0)
        app = FastAPI()

        # Add a middleware that sets user_id before rate limiter runs
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
        from starlette.requests import Request
        from starlette.responses import Response

        class SetUserMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self, request: Request, call_next: RequestResponseEndpoint
            ) -> Response:
                request.state.user_id = "user-abc-123"
                return await call_next(request)

        app.add_middleware(RateLimitMiddleware, redis_client=mock_redis, config=RateLimitConfig())
        app.add_middleware(SetUserMiddleware)

        @app.get("/api/data")
        async def get_data() -> dict[str, str]:
            return {"data": "ok"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.status_code == 200

        # Verify the Redis pipeline was called (meaning rate limiting ran)
        mock_redis.pipeline.assert_called()

    async def test_uses_ip_when_no_user_id(self) -> None:
        """When no user_id, should fallback to IP-based rate limiting."""
        mock_redis = _create_mock_redis(current_count=0)
        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.status_code == 200

        # Verify the Redis pipeline was called (rate limiting ran with IP key)
        mock_redis.pipeline.assert_called()


class TestRateLimitPathConfig:
    """Tests for path-specific rate limits."""

    async def test_auth_endpoints_use_auth_limit(self) -> None:
        """Auth endpoints should use the lower auth_rpm limit."""
        # Set count to 10 (at the auth limit of 10)
        mock_redis = _create_mock_redis(current_count=10)
        config = RateLimitConfig(default_rpm=100, auth_rpm=10)
        app = _create_test_app(mock_redis, config=config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/login")
            assert resp.status_code == 429

    async def test_regular_endpoints_use_default_limit(self) -> None:
        """Regular endpoints should use the higher default_rpm limit."""
        # Set count to 10 (under default limit of 100, but at auth limit)
        mock_redis = _create_mock_redis(current_count=10)
        config = RateLimitConfig(default_rpm=100, auth_rpm=10)
        app = _create_test_app(mock_redis, config=config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.status_code == 200


class TestRateLimitRedisError:
    """Tests for graceful handling of Redis errors."""

    async def test_redis_error_allows_request_through(self) -> None:
        """If Redis fails, fail open — allow the request through."""
        mock_redis = AsyncMock()
        pipe = AsyncMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        mock_redis.pipeline = MagicMock(return_value=pipe)

        app = _create_test_app(mock_redis)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/data")
            assert resp.status_code == 200
