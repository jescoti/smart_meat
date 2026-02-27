"""Tests for Google OAuth service — thin wrapper over Google's HTTP endpoints.

TDD RED phase — these tests are written before the implementation.
All external HTTP calls are mocked.

Note: httpx.Response methods (.json(), .raise_for_status()) are synchronous,
so we use MagicMock for response objects.  The client's .post()/.get() methods
are async, so we use AsyncMock for the client.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.google_auth import (
    build_authorization_url,
    exchange_code_for_tokens,
    fetch_user_info,
    refresh_access_token,
    revoke_token,
)

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "test-client-secret"
REDIRECT_URI = "http://localhost:8000/api/auth/callback"
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def _make_mock_response(*, status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    """Create a MagicMock that behaves like an httpx.Response.

    Uses MagicMock (not AsyncMock) because httpx.Response methods are sync.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


def _make_error_response(*, status_code: int = 400, message: str = "Bad Request") -> MagicMock:
    """Create a MagicMock that raises HTTPStatusError on raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message, request=MagicMock(), response=resp
    )
    return resp


class TestBuildAuthorizationUrl:
    """Tests for build_authorization_url()."""

    def test_returns_string(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert isinstance(url, str)

    def test_contains_google_auth_endpoint(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "accounts.google.com/o/oauth2/v2/auth" in url

    def test_contains_client_id(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert f"client_id={CLIENT_ID}" in url

    def test_contains_redirect_uri(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "redirect_uri=" in url

    def test_contains_state(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "state=state123" in url

    def test_contains_scopes(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "scope=" in url
        assert "openid" in url
        assert "email" in url
        assert "profile" in url

    def test_response_type_is_code(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "response_type=code" in url

    def test_access_type_is_offline(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "access_type=offline" in url

    def test_prompt_is_consent(self) -> None:
        url = build_authorization_url(CLIENT_ID, REDIRECT_URI, "state123", SCOPES)
        assert "prompt=consent" in url


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens()."""

    @pytest.fixture
    def token_data(self) -> dict:
        return {
            "access_token": "ya29.test-access-token",
            "refresh_token": "1//test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid email profile",
        }

    async def test_returns_token_dict(self, token_data: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=token_data)

        result = await exchange_code_for_tokens(
            "auth-code-123", CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, client=mock_client
        )
        assert result["access_token"] == "ya29.test-access-token"
        assert result["refresh_token"] == "1//test-refresh-token"

    async def test_posts_to_google_token_endpoint(self, token_data: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=token_data)

        await exchange_code_for_tokens(
            "auth-code-123", CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, client=mock_client
        )
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "oauth2.googleapis.com/token" in call_args[0][0]

    async def test_sends_correct_form_data(self, token_data: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=token_data)

        await exchange_code_for_tokens(
            "auth-code-123", CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, client=mock_client
        )
        call_kwargs = mock_client.post.call_args
        form_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert form_data["code"] == "auth-code-123"
        assert form_data["client_id"] == CLIENT_ID
        assert form_data["client_secret"] == CLIENT_SECRET
        assert form_data["redirect_uri"] == REDIRECT_URI
        assert form_data["grant_type"] == "authorization_code"

    async def test_raises_on_http_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_error_response()

        with pytest.raises(httpx.HTTPStatusError):
            await exchange_code_for_tokens(
                "bad-code", CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, client=mock_client
            )


class TestFetchUserInfo:
    """Tests for fetch_user_info()."""

    @pytest.fixture
    def user_info(self) -> dict:
        return {
            "id": "1234567890",
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }

    async def test_returns_user_info_dict(self, user_info: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(json_data=user_info)

        result = await fetch_user_info("ya29.test-token", client=mock_client)
        assert result["id"] == "1234567890"
        assert result["email"] == "user@example.com"

    async def test_calls_google_userinfo_endpoint(self, user_info: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(json_data=user_info)

        await fetch_user_info("ya29.test-token", client=mock_client)
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "googleapis.com/oauth2/v2/userinfo" in call_args[0][0]

    async def test_passes_authorization_header(self, user_info: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_mock_response(json_data=user_info)

        await fetch_user_info("ya29.test-token", client=mock_client)
        call_kwargs = mock_client.get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Bearer ya29.test-token"

    async def test_raises_on_http_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = _make_error_response(status_code=401, message="Unauthorized")

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_user_info("bad-token", client=mock_client)


class TestRefreshAccessToken:
    """Tests for refresh_access_token()."""

    @pytest.fixture
    def refresh_response(self) -> dict:
        return {
            "access_token": "ya29.new-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid email profile",
        }

    async def test_returns_new_token_dict(self, refresh_response: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=refresh_response)

        result = await refresh_access_token(
            "1//refresh-token", CLIENT_ID, CLIENT_SECRET, client=mock_client
        )
        assert result["access_token"] == "ya29.new-access-token"

    async def test_posts_to_google_token_endpoint(self, refresh_response: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=refresh_response)

        await refresh_access_token("1//refresh-token", CLIENT_ID, CLIENT_SECRET, client=mock_client)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "oauth2.googleapis.com/token" in call_args[0][0]

    async def test_sends_correct_form_data(self, refresh_response: dict) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response(json_data=refresh_response)

        await refresh_access_token("1//refresh-token", CLIENT_ID, CLIENT_SECRET, client=mock_client)
        call_kwargs = mock_client.post.call_args
        form_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert form_data["refresh_token"] == "1//refresh-token"
        assert form_data["client_id"] == CLIENT_ID
        assert form_data["client_secret"] == CLIENT_SECRET
        assert form_data["grant_type"] == "refresh_token"

    async def test_raises_on_http_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_error_response()

        with pytest.raises(httpx.HTTPStatusError):
            await refresh_access_token(
                "bad-refresh-token", CLIENT_ID, CLIENT_SECRET, client=mock_client
            )


class TestRevokeToken:
    """Tests for revoke_token()."""

    async def test_returns_true_on_success(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response()

        result = await revoke_token("ya29.test-token", client=mock_client)
        assert result is True

    async def test_posts_to_google_revoke_endpoint(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response()

        await revoke_token("ya29.test-token", client=mock_client)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "oauth2.googleapis.com/revoke" in call_args[0][0]

    async def test_sends_token_in_params(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_mock_response()

        await revoke_token("ya29.test-token", client=mock_client)
        call_kwargs = mock_client.post.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["token"] == "ya29.test-token"

    async def test_returns_false_on_http_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = _make_error_response()

        result = await revoke_token("bad-token", client=mock_client)
        assert result is False
