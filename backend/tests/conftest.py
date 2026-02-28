"""Pytest configuration and shared fixtures for backend tests."""

import os

import pytest

# Set required env vars before any app module is imported.
# These are dummy values used only for tests — they never reach real services.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-tests")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")


# Configure pytest-asyncio to use asyncio mode automatically
# This is required for all async test functions
