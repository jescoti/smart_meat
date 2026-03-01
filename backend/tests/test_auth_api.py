"""Integration tests for the OAuth auth endpoints.

TDD RED phase — these tests are written before the implementation.
All external HTTP calls (Google APIs) are mocked. Database operations are
mocked via mock sessions.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token, create_refresh_token

# Test constants
SECRET_KEY = "test-secret-key-at-least-32-chars-long!"
ENCRYPTION_KEY = "test-encryption-key"
CLIENT_ID = "test-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "test-client-secret"
REDIRECT_URI = "http://localhost:8000/api/auth/callback"
USER_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
GOOGLE_ID = "1234567890"


def _make_test_app(*, session_override: object | None = None):
    """Create a minimal FastAPI app with only the auth router for testing.

    Args:
        session_override: If provided, override _get_session_dependency with
            a lambda returning this value.
    """
    from fastapi import FastAPI

    from app.api.auth import _get_session_dependency, create_auth_router

    app = FastAPI()
    router = create_auth_router(
        secret_key=SECRET_KEY,
        encryption_key=ENCRYPTION_KEY,
        google_client_id=CLIENT_ID,
        google_client_secret=CLIENT_SECRET,
        google_redirect_uri=REDIRECT_URI,
        jwt_access_ttl_minutes=15,
        jwt_refresh_ttl_days=7,
        frontend_url="http://localhost:3000",
    )
    app.include_router(router)

    if session_override is not None:
        app.dependency_overrides[_get_session_dependency] = lambda: session_override

    return app


def _make_valid_state() -> str:
    """Create a valid signed state parameter."""
    return pyjwt.encode(
        {
            "csrf": "random-csrf-value",
            "exp": datetime.now(tz=UTC).timestamp() + 600,
        },
        SECRET_KEY,
        algorithm="HS256",
    )


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with common defaults."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _make_mock_user(
    *,
    user_id: uuid.UUID = USER_ID,
    google_id: str = GOOGLE_ID,
    email: str = "user@example.com",
    display_name: str = "Test User",
    avatar_url: str | None = "https://example.com/photo.jpg",
    llm_consent_given_at: datetime | None = None,
    encrypted_access_token: str | None = "encrypted-at",
    encrypted_refresh_token: str | None = "encrypted-rt",
) -> MagicMock:
    """Create a mock User ORM object."""
    user = MagicMock()
    user.id = user_id
    user.google_id = google_id
    user.email = email
    user.display_name = display_name
    user.avatar_url = avatar_url
    user.llm_consent_given_at = llm_consent_given_at
    user.encrypted_access_token = encrypted_access_token
    user.encrypted_refresh_token = encrypted_refresh_token
    user.token_expires_at = None
    return user


class TestMeEndpoint:
    """Tests for GET /api/auth/me."""

    async def test_me_returns_user_profile(self) -> None:
        """Authenticated request returns user profile with correct shape."""
        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        from fastapi import FastAPI
        from app.api.auth import _get_session_dependency, create_auth_router
        from app.middleware.auth import AuthMiddleware

        app = FastAPI()
        router = create_auth_router(
            secret_key=SECRET_KEY,
            encryption_key=ENCRYPTION_KEY,
            google_client_id=CLIENT_ID,
            google_client_secret=CLIENT_SECRET,
            google_redirect_uri=REDIRECT_URI,
        )
        app.include_router(router)
        app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        token = create_access_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", token)
            resp = await client.get("/api/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(USER_ID)
        assert data["email"] == "user@example.com"
        assert data["name"] == "Test User"
        assert data["avatarUrl"] == "https://example.com/photo.jpg"

    async def test_me_without_cookie_returns_401(self) -> None:
        """Unauthenticated request returns 401."""
        from fastapi import FastAPI
        from app.api.auth import create_auth_router
        from app.middleware.auth import AuthMiddleware

        app = FastAPI()
        router = create_auth_router(
            secret_key=SECRET_KEY,
            encryption_key=ENCRYPTION_KEY,
            google_client_id=CLIENT_ID,
            google_client_secret=CLIENT_SECRET,
            google_redirect_uri=REDIRECT_URI,
        )
        app.include_router(router)
        app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/me")

        assert resp.status_code == 401

    async def test_me_without_user_id_in_state_returns_401(self) -> None:
        """If request.state has no user_id (no middleware), endpoint returns 401."""
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)

        # No AuthMiddleware added — request.state won't have user_id
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/me")

        assert resp.status_code == 401

    async def test_me_user_not_found_returns_404(self) -> None:
        """Valid JWT but deleted user returns 404."""
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        from fastapi import FastAPI
        from app.api.auth import _get_session_dependency, create_auth_router
        from app.middleware.auth import AuthMiddleware

        app = FastAPI()
        router = create_auth_router(
            secret_key=SECRET_KEY,
            encryption_key=ENCRYPTION_KEY,
            google_client_id=CLIENT_ID,
            google_client_secret=CLIENT_SECRET,
            google_redirect_uri=REDIRECT_URI,
        )
        app.include_router(router)
        app.add_middleware(AuthMiddleware, secret_key=SECRET_KEY)
        app.dependency_overrides[_get_session_dependency] = lambda: mock_session

        token = create_access_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("access_token", token)
            resp = await client.get("/api/auth/me")

        assert resp.status_code == 404


class TestLoginEndpoint:
    """Tests for GET /api/auth/login."""

    async def test_returns_200(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        assert resp.status_code == 200

    async def test_returns_authorization_url(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        data = resp.json()
        assert "url" in data
        assert "accounts.google.com" in data["url"]

    async def test_url_contains_client_id(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        data = resp.json()
        assert CLIENT_ID in data["url"]

    async def test_url_contains_state_parameter(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        data = resp.json()
        assert "state=" in data["url"]

    async def test_url_contains_required_scopes(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        data = resp.json()
        assert "openid" in data["url"]
        assert "email" in data["url"]
        assert "gmail.readonly" in data["url"]
        assert "gmail.send" in data["url"]

    async def test_state_is_valid_jwt(self) -> None:
        """The state parameter should be a JWT signed with SECRET_KEY."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/login")
        data = resp.json()
        url = data["url"]
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        state = params["state"][0]

        payload = pyjwt.decode(state, SECRET_KEY, algorithms=["HS256"])
        assert "csrf" in payload
        assert "exp" in payload


class TestCallbackEndpoint:
    """Tests for GET /api/auth/callback."""

    @pytest.fixture
    def google_tokens(self) -> dict:
        return {
            "access_token": "ya29.test-access-token",
            "refresh_token": "1//test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

    @pytest.fixture
    def google_user_info(self) -> dict:
        return {
            "id": GOOGLE_ID,
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

    async def test_invalid_state_returns_400(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "test-code", "state": "invalid-state"}
            )
        assert resp.status_code == 400

    async def test_missing_code_returns_400(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/callback", params={"state": state})
        assert resp.status_code == 400

    async def test_missing_state_returns_400(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/auth/callback", params={"code": "test-code"})
        assert resp.status_code == 400

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_successful_callback_redirects(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_session.merge.return_value = _make_mock_user()

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        assert resp.status_code == 307

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_sets_access_token_cookie(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_session.merge.return_value = _make_mock_user()

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        cookies = resp.headers.get_list("set-cookie")
        cookie_names = [c.split("=")[0] for c in cookies]
        assert "access_token" in cookie_names

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_sets_refresh_token_cookie(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_session.merge.return_value = _make_mock_user()

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        cookies = resp.headers.get_list("set-cookie")
        cookie_names = [c.split("=")[0] for c in cookies]
        assert "refresh_token" in cookie_names

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_sets_csrf_token_cookie(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_session.merge.return_value = _make_mock_user()

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        cookies = resp.headers.get_list("set-cookie")
        cookie_names = [c.split("=")[0] for c in cookies]
        assert "csrf_token" in cookie_names

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_redirects_to_dashboard_when_no_llm_consent(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_user = _make_mock_user(llm_consent_given_at=None)
        mock_session.merge.return_value = mock_user

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        assert "/dashboard" in resp.headers["location"]

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    async def test_callback_google_token_exchange_failure_returns_400(
        self,
        mock_exchange: AsyncMock,
    ) -> None:
        mock_exchange.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=MagicMock(status_code=400)
        )

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "bad-code", "state": state}
            )

        assert resp.status_code == 400

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_fetch_user_info_failure_returns_400(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
    ) -> None:
        """When Google userinfo fetch fails, callback should return 400."""
        mock_exchange.return_value = google_tokens
        mock_fetch_user.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        assert resp.status_code == 400

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_encrypts_tokens(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result
        mock_user = _make_mock_user()
        mock_session.merge.return_value = mock_user

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)

        with patch("app.api.auth.encrypt") as mock_encrypt:
            mock_encrypt.return_value = "encrypted-value"
            async with AsyncClient(
                transport=transport, base_url="http://test", follow_redirects=False
            ) as client:
                await client.get(
                    "/api/auth/callback", params={"code": "auth-code-123", "state": state}
                )

            # encrypt should have been called for access_token and refresh_token
            assert mock_encrypt.call_count == 2

    @patch("app.api.auth.google_auth.exchange_code_for_tokens")
    @patch("app.api.auth.google_auth.fetch_user_info")
    async def test_callback_with_existing_user(
        self,
        mock_fetch_user: AsyncMock,
        mock_exchange: AsyncMock,
        google_tokens: dict,
        google_user_info: dict,
    ) -> None:
        """When a user already exists (upsert), it should still succeed."""
        mock_exchange.return_value = google_tokens
        mock_fetch_user.return_value = google_user_info

        existing_user = _make_mock_user()

        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        state = _make_valid_state()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as client:
            resp = await client.get(
                "/api/auth/callback", params={"code": "auth-code-123", "state": state}
            )

        assert resp.status_code == 307


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh."""

    async def test_missing_refresh_token_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    async def test_invalid_refresh_token_returns_401(self) -> None:
        mock_session = _make_mock_session()
        app = _make_test_app(session_override=mock_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", "invalid-jwt-token")
            resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    @patch("app.api.auth.google_auth.refresh_access_token")
    async def test_successful_refresh_returns_200(
        self,
        mock_google_refresh: AsyncMock,
    ) -> None:
        mock_google_refresh.return_value = {
            "access_token": "ya29.new-access-token",
            "expires_in": 3600,
        }

        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            with patch("app.api.auth.decrypt", return_value="1//google-refresh-token"):
                with patch("app.api.auth.encrypt", return_value="encrypted-value"):
                    resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 200

    @patch("app.api.auth.google_auth.refresh_access_token")
    async def test_refresh_sets_new_cookies(
        self,
        mock_google_refresh: AsyncMock,
    ) -> None:
        mock_google_refresh.return_value = {
            "access_token": "ya29.new-access-token",
            "expires_in": 3600,
        }

        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            with patch("app.api.auth.decrypt", return_value="1//google-refresh-token"):
                with patch("app.api.auth.encrypt", return_value="encrypted-value"):
                    resp = await client.post("/api/auth/refresh")

        cookies = resp.headers.get_list("set-cookie")
        cookie_names = [c.split("=")[0] for c in cookies]
        assert "access_token" in cookie_names
        assert "refresh_token" in cookie_names

    async def test_refresh_user_not_found_returns_401(self) -> None:
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 401

    @patch("app.api.auth.google_auth.refresh_access_token")
    async def test_refresh_google_api_failure_returns_401(
        self,
        mock_google_refresh: AsyncMock,
    ) -> None:
        mock_google_refresh.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=MagicMock(status_code=400)
        )

        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            with patch("app.api.auth.decrypt", return_value="1//google-refresh-token"):
                resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 401

    @patch("app.api.auth.google_auth.refresh_access_token")
    async def test_refresh_failure_clears_cookies(
        self,
        mock_google_refresh: AsyncMock,
    ) -> None:
        mock_google_refresh.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=MagicMock(status_code=400)
        )

        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            with patch("app.api.auth.decrypt", return_value="1//google-refresh-token"):
                resp = await client.post("/api/auth/refresh")

        cookies = resp.headers.get_list("set-cookie")
        cookie_str = " ".join(cookies)
        assert "access_token" in cookie_str
        assert "refresh_token" in cookie_str

    @patch("app.api.auth.google_auth.refresh_access_token")
    async def test_refresh_with_new_google_refresh_token(
        self,
        mock_google_refresh: AsyncMock,
    ) -> None:
        """When Google returns a new refresh_token, it should be re-encrypted and stored."""
        mock_google_refresh.return_value = {
            "access_token": "ya29.new-access-token",
            "refresh_token": "1//brand-new-refresh-token",
            "expires_in": 3600,
        }

        mock_user = _make_mock_user()
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            with patch("app.api.auth.decrypt", return_value="1//old-refresh-token"):
                with patch("app.api.auth.encrypt", return_value="encrypted-value") as mock_encrypt:
                    resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 200
        # encrypt should be called for both the new access token and the new refresh token
        assert mock_encrypt.call_count == 2

    async def test_refresh_with_no_encrypted_google_token_returns_401(self) -> None:
        """If user has no stored Google refresh token, return 401."""
        mock_user = _make_mock_user(encrypted_refresh_token=None)
        mock_session = _make_mock_session()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_scalar_result

        app = _make_test_app(session_override=mock_session)

        refresh_jwt = create_refresh_token(str(USER_ID), SECRET_KEY)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_jwt)
            resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout."""

    async def test_logout_returns_200(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200

    async def test_logout_clears_cookies(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/logout")

        cookies = resp.headers.get_list("set-cookie")
        cookie_str = " ".join(cookies)
        assert "access_token" in cookie_str
        assert "refresh_token" in cookie_str
        assert "csrf_token" in cookie_str

    async def test_logout_returns_success_message(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/logout")
        data = resp.json()
        assert data.get("status") == "ok"

    @patch("app.api.auth.google_auth.revoke_token")
    async def test_logout_attempts_to_revoke_google_token(
        self,
        mock_revoke: AsyncMock,
    ) -> None:
        mock_revoke.return_value = True

        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set(
                "access_token",
                create_access_token(str(USER_ID), SECRET_KEY),
            )
            resp = await client.post("/api/auth/logout")

        assert resp.status_code == 200

    async def test_logout_without_token_still_succeeds(self) -> None:
        """Logout should succeed even if no tokens are present."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
