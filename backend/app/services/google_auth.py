"""Google OAuth service — thin wrapper over Google's HTTP OAuth endpoints.

All functions use ``httpx.AsyncClient`` for HTTP calls.  An optional *client*
parameter allows tests to inject a mock client.

Google OAuth endpoints:
    - Authorization: https://accounts.google.com/o/oauth2/v2/auth
    - Token:         https://oauth2.googleapis.com/token
    - Userinfo:      https://www.googleapis.com/oauth2/v2/userinfo
    - Revoke:        https://oauth2.googleapis.com/revoke
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: list[str],
) -> str:
    """Build a Google OAuth 2.0 authorization URL.

    Args:
        client_id: Google OAuth client ID.
        redirect_uri: Callback URL after authorization.
        state: Anti-CSRF state parameter (should be a signed JWT).
        scopes: List of OAuth scopes to request.

    Returns:
        The full authorization URL to redirect the user to.
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Exchange an authorization code for access and refresh tokens.

    Args:
        code: The authorization code from the callback.
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.
        redirect_uri: The same redirect URI used in the authorization request.
        client: Optional httpx client (injected for testing).

    Returns:
        Token response dict with ``access_token``, ``refresh_token``, etc.

    Raises:
        httpx.HTTPStatusError: If the token endpoint returns an error.
    """
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    if client is not None:
        resp = await client.post(_TOKEN_ENDPOINT, data=data)
        resp.raise_for_status()
        return resp.json()

    async with httpx.AsyncClient() as http_client:  # pragma: no cover
        resp = await http_client.post(_TOKEN_ENDPOINT, data=data)
        resp.raise_for_status()
        return resp.json()


async def fetch_user_info(
    access_token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch the authenticated user's profile from Google.

    Args:
        access_token: A valid Google access token.
        client: Optional httpx client (injected for testing).

    Returns:
        User info dict with ``id``, ``email``, ``name``, ``picture``.

    Raises:
        httpx.HTTPStatusError: If the userinfo endpoint returns an error.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    if client is not None:
        resp = await client.get(_USERINFO_ENDPOINT, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async with httpx.AsyncClient() as http_client:  # pragma: no cover
        resp = await http_client.get(_USERINFO_ENDPOINT, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Use a refresh token to obtain a new access token from Google.

    Args:
        refresh_token: The Google refresh token.
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.
        client: Optional httpx client (injected for testing).

    Returns:
        Token response dict with ``access_token``, ``expires_in``, etc.

    Raises:
        httpx.HTTPStatusError: If the token endpoint returns an error.
    """
    data = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }

    if client is not None:
        resp = await client.post(_TOKEN_ENDPOINT, data=data)
        resp.raise_for_status()
        return resp.json()

    async with httpx.AsyncClient() as http_client:  # pragma: no cover
        resp = await http_client.post(_TOKEN_ENDPOINT, data=data)
        resp.raise_for_status()
        return resp.json()


async def revoke_token(
    token: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Revoke a Google OAuth token.

    Args:
        token: The access or refresh token to revoke.
        client: Optional httpx client (injected for testing).

    Returns:
        True if revocation succeeded, False otherwise.
    """
    params = {"token": token}

    try:
        if client is not None:
            resp = await client.post(_REVOKE_ENDPOINT, params=params)
            resp.raise_for_status()
        else:
            async with httpx.AsyncClient() as http_client:  # pragma: no cover
                resp = await http_client.post(_REVOKE_ENDPOINT, params=params)
                resp.raise_for_status()
    except httpx.HTTPStatusError:
        return False

    return True
