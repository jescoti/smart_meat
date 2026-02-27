"""Redis-backed sliding window rate limiter middleware for FastAPI.

Enforces per-user (or per-IP fallback) rate limits using Redis as the
counter store.  Different path prefixes can have different limits (e.g.
auth endpoints are stricter than general API endpoints).

On Redis failure, the middleware fails open — requests are allowed through
rather than blocking all traffic.
"""

from __future__ import annotations

from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for rate limit thresholds.

    All limits are expressed as requests per minute (RPM).
    """

    default_rpm: int = 100
    auth_rpm: int = 10
    reply_rpm: int = 10
    llm_rpm: int = 20
    window_seconds: int = 60


# Path prefix → config attribute name mapping for path-specific limits.
_PATH_LIMIT_MAP: list[tuple[str, str]] = [
    ("/api/auth/", "auth_rpm"),
    ("/api/reply/", "reply_rpm"),
    ("/api/llm/", "llm_rpm"),
]


def _get_limit_for_path(path: str, config: RateLimitConfig) -> int:
    """Determine the rate limit for a given request path.

    Checks path prefixes in order; returns the first match.
    Falls back to ``config.default_rpm`` if no prefix matches.
    """
    for prefix, attr in _PATH_LIMIT_MAP:
        if path.startswith(prefix):
            return getattr(config, attr)
    return config.default_rpm


def _get_rate_key(request: Request, path: str, config: RateLimitConfig) -> str:
    """Build the Redis key for rate limiting.

    Uses ``user_id`` from request state if available, otherwise falls back
    to the client IP address.  The key includes the path-bucket so different
    endpoint groups have independent counters.
    """
    # Determine the bucket name for this path
    bucket = "default"
    for prefix, attr in _PATH_LIMIT_MAP:
        if path.startswith(prefix):
            bucket = attr.replace("_rpm", "")
            break

    # Prefer user_id, fall back to IP
    identity: str
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        identity = f"user:{user_id}"
    else:
        client = request.client
        ip = client.host if client else "unknown"
        identity = f"ip:{ip}"

    return f"rate_limit:{bucket}:{identity}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for Redis-backed sliding-window rate limiting.

    Constructor Args:
        app: The ASGI application.
        redis_client: An async Redis client instance (``redis.asyncio.Redis``).
        config: Rate limit configuration.  Defaults to ``RateLimitConfig()``.
    """

    def __init__(
        self,
        app: object,
        redis_client: object,
        config: RateLimitConfig | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._redis = redis_client
        self._config = config or RateLimitConfig()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        limit = _get_limit_for_path(path, self._config)
        key = _get_rate_key(request, path, self._config)

        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._config.window_seconds)
            result = await pipe.execute()
            current_count: int = result[0]
        except Exception:
            # Fail open: if Redis is unavailable, allow the request through.
            return await call_next(request)

        if current_count > limit:
            ttl = await self._redis.ttl(key)
            retry_after = max(ttl, 1)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
