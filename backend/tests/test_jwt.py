"""Tests for JWT token creation and verification.

TDD RED phase — these tests are written before the implementation.
"""

import time

import jwt as pyjwt
import pytest

from app.auth.jwt import create_access_token, create_refresh_token, verify_token

SECRET = "test-secret-key-for-jwt"
USER_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_string(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        assert isinstance(token, str)

    def test_payload_contains_sub(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == USER_ID

    def test_payload_contains_type_access(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["type"] == "access"

    def test_payload_contains_exp(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert "exp" in payload

    def test_payload_contains_iat(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert "iat" in payload

    def test_default_ttl_15_minutes(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        # exp should be ~15 minutes from iat
        delta = payload["exp"] - payload["iat"]
        assert delta == 15 * 60

    def test_custom_ttl(self) -> None:
        token = create_access_token(USER_ID, SECRET, ttl_minutes=30)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        delta = payload["exp"] - payload["iat"]
        assert delta == 30 * 60

    def test_different_users_produce_different_tokens(self) -> None:
        token1 = create_access_token(USER_ID, SECRET)
        token2 = create_access_token("another-user-id", SECRET)
        assert token1 != token2


class TestCreateRefreshToken:
    """Tests for create_refresh_token()."""

    def test_returns_string(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        assert isinstance(token, str)

    def test_payload_contains_sub(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == USER_ID

    def test_payload_contains_type_refresh(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["type"] == "refresh"

    def test_payload_contains_exp(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert "exp" in payload

    def test_payload_contains_iat(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        assert "iat" in payload

    def test_default_ttl_7_days(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        delta = payload["exp"] - payload["iat"]
        assert delta == 7 * 24 * 60 * 60

    def test_custom_ttl(self) -> None:
        token = create_refresh_token(USER_ID, SECRET, ttl_days=14)
        payload = pyjwt.decode(token, SECRET, algorithms=["HS256"])
        delta = payload["exp"] - payload["iat"]
        assert delta == 14 * 24 * 60 * 60


class TestVerifyToken:
    """Tests for verify_token()."""

    def test_valid_access_token(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = verify_token(token, SECRET)
        assert payload["sub"] == USER_ID
        assert payload["type"] == "access"

    def test_valid_refresh_token(self) -> None:
        token = create_refresh_token(USER_ID, SECRET)
        payload = verify_token(token, SECRET)
        assert payload["sub"] == USER_ID
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self) -> None:
        token = create_access_token(USER_ID, SECRET, ttl_minutes=0)
        # Token with 0 TTL should be expired immediately
        with pytest.raises(ValueError, match="expired"):
            verify_token(token, SECRET)

    def test_wrong_secret_raises(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        with pytest.raises(ValueError, match="invalid"):
            verify_token(token, "wrong-secret-key")

    def test_malformed_token_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            verify_token("not.a.valid.jwt", SECRET)

    def test_empty_token_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            verify_token("", SECRET)

    def test_returns_dict(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = verify_token(token, SECRET)
        assert isinstance(payload, dict)

    def test_payload_has_expected_keys(self) -> None:
        token = create_access_token(USER_ID, SECRET)
        payload = verify_token(token, SECRET)
        assert "sub" in payload
        assert "type" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_tampered_payload_raises(self) -> None:
        """A token signed with a different key should fail verification."""
        # Create a token with a different secret
        tampered = pyjwt.encode(
            {"sub": USER_ID, "type": "access", "exp": time.time() + 3600, "iat": time.time()},
            "different-secret",
            algorithm="HS256",
        )
        with pytest.raises(ValueError, match="invalid"):
            verify_token(tampered, SECRET)
