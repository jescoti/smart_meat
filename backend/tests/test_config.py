"""Tests for app configuration settings — written FIRST (TDD Red phase)."""

import pytest
from unittest.mock import patch


def test_settings_loads_from_env_vars() -> None:
    """Settings class must read all required fields from environment variables."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/testdb"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.SECRET_KEY == "test-secret-key"
        assert settings.ENCRYPTION_KEY == "test-encryption-key-32-bytes-long"
        assert settings.GOOGLE_CLIENT_ID == "test-google-client-id"
        assert settings.GOOGLE_CLIENT_SECRET == "test-google-client-secret"
        assert settings.ANTHROPIC_API_KEY == "test-anthropic-key"


def test_settings_defaults() -> None:
    """Settings class must have correct default values for optional fields."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert settings.GOOGLE_REDIRECT_URI == "http://localhost:8000/api/auth/callback"
        assert settings.CLAUDE_MODEL == "claude-sonnet-4-5-20250514"
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]
        assert settings.JWT_ACCESS_TOKEN_TTL_MINUTES == 15
        assert settings.JWT_REFRESH_TOKEN_TTL_DAYS == 7


def test_settings_cors_origins_override() -> None:
    """CORS_ORIGINS can be overridden via environment variable."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "CORS_ORIGINS": '["http://localhost:3000","http://localhost:3001"]',
    }
    with patch.dict("os.environ", env_vars, clear=False):
        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert "http://localhost:3000" in settings.CORS_ORIGINS
        assert "http://localhost:3001" in settings.CORS_ORIGINS


def test_settings_jwt_ttl_override() -> None:
    """JWT TTL values can be overridden via environment variables."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "JWT_ACCESS_TOKEN_TTL_MINUTES": "30",
        "JWT_REFRESH_TOKEN_TTL_DAYS": "14",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert settings.JWT_ACCESS_TOKEN_TTL_MINUTES == 30
        assert settings.JWT_REFRESH_TOKEN_TTL_DAYS == 14


def test_settings_google_redirect_uri_override() -> None:
    """GOOGLE_REDIRECT_URI can be overridden via environment variable."""
    env_vars = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key",
        "ENCRYPTION_KEY": "test-encryption-key-32-bytes-long",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "GOOGLE_REDIRECT_URI": "https://example.com/api/auth/callback",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert settings.GOOGLE_REDIRECT_URI == "https://example.com/api/auth/callback"
