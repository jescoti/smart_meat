"""JWT token creation and verification.

Provides helpers to create and verify HS256-signed JSON Web Tokens for
authentication.  Access tokens are short-lived (default 15 min); refresh
tokens are long-lived (default 7 days).

Uses the PyJWT library (``import jwt``).
"""

from datetime import UTC, datetime

import jwt


def create_access_token(
    user_id: str,
    secret_key: str,
    ttl_minutes: int = 15,
) -> str:
    """Create a short-lived JWT access token.

    Args:
        user_id: The user's unique identifier (stored in the ``sub`` claim).
        secret_key: HMAC secret used to sign the token.
        ttl_minutes: Token lifetime in minutes.  Defaults to 15.

    Returns:
        An encoded JWT string.
    """
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + ttl_minutes * 60,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def create_refresh_token(
    user_id: str,
    secret_key: str,
    ttl_days: int = 7,
) -> str:
    """Create a long-lived JWT refresh token.

    Args:
        user_id: The user's unique identifier (stored in the ``sub`` claim).
        secret_key: HMAC secret used to sign the token.
        ttl_days: Token lifetime in days.  Defaults to 7.

    Returns:
        An encoded JWT string.
    """
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + ttl_days * 24 * 60 * 60,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def verify_token(token: str, secret_key: str) -> dict[str, object]:
    """Verify and decode a JWT token.

    Args:
        token: The encoded JWT string.
        secret_key: The HMAC secret that was used to sign the token.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        ValueError: If the token is expired, has an invalid signature, or is
            otherwise malformed.
    """
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Token is invalid") from exc
    return payload
