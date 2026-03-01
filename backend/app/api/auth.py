"""OAuth authentication endpoints.

Provides Google OAuth login, callback, token refresh, and logout.  All
sensitive tokens are encrypted before storage, and JWTs are issued as
httpOnly cookies.

The router is created via ``create_auth_router()`` which accepts all
configuration as parameters for testability (no module-level singleton
dependency).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, create_refresh_token, verify_token
from app.crypto import decrypt, encrypt
from app.db.models import AuditLog, User
from app.middleware.csrf import generate_csrf_token
from app.services import google_auth

# OAuth scopes required by the application.
_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


async def _get_session_dependency() -> AsyncSession:  # pragma: no cover
    """Placeholder dependency — overridden in tests and by the real app."""
    raise NotImplementedError("Must override _get_session_dependency")


def create_auth_router(
    *,
    secret_key: str,
    encryption_key: str,
    google_client_id: str,
    google_client_secret: str,
    google_redirect_uri: str,
    jwt_access_ttl_minutes: int = 15,
    jwt_refresh_ttl_days: int = 7,
    frontend_url: str = "http://localhost:3000",
    dev_login_enabled: bool = False,
) -> APIRouter:
    """Create an APIRouter with OAuth endpoints, configured with the given settings.

    Args:
        secret_key: HMAC secret for signing JWTs and state tokens.
        encryption_key: Key for AES-256-GCM encryption of Google tokens.
        google_client_id: Google OAuth client ID.
        google_client_secret: Google OAuth client secret.
        google_redirect_uri: Callback URL for Google OAuth.
        jwt_access_ttl_minutes: JWT access token lifetime in minutes.
        jwt_refresh_ttl_days: JWT refresh token lifetime in days.
        frontend_url: Base URL of the frontend for redirect targets.

    Returns:
        A configured FastAPI APIRouter.
    """
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.get("/login")
    async def login() -> dict[str, str]:
        """Return the Google OAuth authorization URL for the frontend to redirect to."""
        state = pyjwt.encode(
            {
                "csrf": secrets.token_urlsafe(16),
                "exp": datetime.now(tz=UTC).timestamp() + 600,  # 10 minutes
            },
            secret_key,
            algorithm="HS256",
        )
        url = google_auth.build_authorization_url(
            google_client_id, google_redirect_uri, state, _SCOPES
        )
        return {"url": url}

    _session_dep = Depends(_get_session_dependency)

    @router.get("/me")
    async def me(
        request: Request,
        session: AsyncSession = _session_dep,
    ) -> dict:
        """Return the current authenticated user's profile.

        Uses request.state.user_id set by AuthMiddleware. Returns 404
        if the user_id from the JWT no longer exists in the database.
        """
        user_id = getattr(request.state, "user_id", None)
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Not authenticated"},
            )

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "User not found"},
            )

        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.display_name,
            "avatarUrl": user.avatar_url,
        }

    @router.get("/callback")
    async def callback(
        code: str | None = Query(default=None),
        state: str | None = Query(default=None),
        session: AsyncSession = _session_dep,
    ) -> Response:
        """Handle the Google OAuth callback.

        Verifies the state parameter, exchanges the code for tokens, creates or
        updates the user, sets auth cookies, and redirects to the frontend.
        """
        # Validate required parameters
        if not code or not state:
            return JSONResponse(
                status_code=400,
                content={"error": "bad_request", "message": "Missing code or state parameter"},
            )

        # Verify state JWT
        try:
            pyjwt.decode(state, secret_key, algorithms=["HS256"])
        except (pyjwt.InvalidTokenError, pyjwt.ExpiredSignatureError):
            return JSONResponse(
                status_code=400,
                content={"error": "bad_request", "message": "Invalid or expired state parameter"},
            )

        # Exchange code for tokens
        try:
            tokens = await google_auth.exchange_code_for_tokens(
                code, google_client_id, google_client_secret, google_redirect_uri
            )
        except httpx.HTTPStatusError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "oauth_error",
                    "message": "Failed to exchange authorization code",
                },
            )

        # Fetch user info
        try:
            user_info = await google_auth.fetch_user_info(tokens["access_token"])
        except httpx.HTTPStatusError:
            return JSONResponse(
                status_code=400,
                content={"error": "oauth_error", "message": "Failed to fetch user info"},
            )

        # Upsert user by google_id
        result = await session.execute(select(User).where(User.google_id == user_info["id"]))
        user = result.scalar_one_or_none()

        google_access_token = tokens["access_token"]
        google_refresh_token = tokens.get("refresh_token", "")
        encrypted_at = encrypt(google_access_token, encryption_key)
        encrypted_rt = encrypt(google_refresh_token, encryption_key)

        expires_at = datetime.now(tz=UTC) + timedelta(seconds=tokens.get("expires_in", 3600))

        if user is None:
            # New user
            user = User(
                google_id=user_info["id"],
                email=user_info["email"],
                display_name=user_info.get("name", ""),
                avatar_url=user_info.get("picture"),
                encrypted_access_token=encrypted_at,
                encrypted_refresh_token=encrypted_rt,
                token_expires_at=expires_at,
            )
            user = await session.merge(user)
        else:
            # Update existing user
            user.email = user_info["email"]
            user.display_name = user_info.get("name", "")
            user.avatar_url = user_info.get("picture")
            user.encrypted_access_token = encrypted_at
            user.encrypted_refresh_token = encrypted_rt
            user.token_expires_at = expires_at

        await session.flush()

        # Record audit log
        audit_entry = AuditLog(
            user_id=user.id,
            action="login",
            resource_type="session",
            resource_id=str(user.id),
            ip_address=None,
        )
        session.add(audit_entry)
        await session.commit()

        # Create JWT tokens
        jwt_access = create_access_token(str(user.id), secret_key, jwt_access_ttl_minutes)
        jwt_refresh = create_refresh_token(str(user.id), secret_key, jwt_refresh_ttl_days)
        csrf_token = generate_csrf_token()

        # Always redirect to dashboard after login
        redirect_path = "/dashboard"

        redirect_url = f"{frontend_url}{redirect_path}"
        response = RedirectResponse(url=redirect_url)

        # Set cookies
        response.set_cookie(
            key="access_token",
            value=jwt_access,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=jwt_access_ttl_minutes * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=jwt_refresh,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=jwt_refresh_ttl_days * 24 * 60 * 60,
        )
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=True,
            samesite="none",
            max_age=jwt_refresh_ttl_days * 24 * 60 * 60,
        )

        return response

    @router.post("/refresh")
    async def refresh(
        request: Request,
        session: AsyncSession = _session_dep,
    ) -> Response:
        """Refresh the JWT access token using the refresh token cookie.

        Also refreshes the Google access token via Google's token endpoint
        and re-encrypts the new token for storage.
        """
        refresh_token_value = request.cookies.get("refresh_token")
        if not refresh_token_value:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing refresh token"},
            )

        # Verify JWT refresh token
        try:
            payload = verify_token(refresh_token_value, secret_key)
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Invalid or expired refresh token"},
            )

        user_id = str(payload["sub"])

        # Look up user
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            return _clear_cookies_response(
                status_code=401,
                content={"error": "unauthorized", "message": "User not found"},
            )

        # Check for stored Google refresh token
        if not user.encrypted_refresh_token:
            return _clear_cookies_response(
                status_code=401,
                content={"error": "unauthorized", "message": "No stored refresh token"},
            )

        # Decrypt stored Google refresh token and use it to get a new access token
        try:
            google_refresh_token = decrypt(user.encrypted_refresh_token, encryption_key)
            new_tokens = await google_auth.refresh_access_token(
                google_refresh_token, google_client_id, google_client_secret
            )
        except (httpx.HTTPStatusError, Exception):
            # Record audit log for failure
            audit_entry = AuditLog(
                user_id=user.id,
                action="refresh_fail",
                resource_type="session",
                resource_id=str(user.id),
                ip_address=None,
            )
            session.add(audit_entry)
            await session.commit()

            return _clear_cookies_response(
                status_code=401,
                content={"error": "unauthorized", "message": "Failed to refresh Google token"},
            )

        # Re-encrypt and store new tokens
        new_google_at = new_tokens["access_token"]
        user.encrypted_access_token = encrypt(new_google_at, encryption_key)
        user.token_expires_at = datetime.now(tz=UTC) + timedelta(
            seconds=new_tokens.get("expires_in", 3600)
        )

        # If Google returned a new refresh token, update it too
        if "refresh_token" in new_tokens:
            user.encrypted_refresh_token = encrypt(new_tokens["refresh_token"], encryption_key)

        # Record audit log
        audit_entry = AuditLog(
            user_id=user.id,
            action="refresh",
            resource_type="session",
            resource_id=str(user.id),
            ip_address=None,
        )
        session.add(audit_entry)
        await session.commit()

        # Issue new JWT tokens
        jwt_access = create_access_token(str(user.id), secret_key, jwt_access_ttl_minutes)
        jwt_refresh = create_refresh_token(str(user.id), secret_key, jwt_refresh_ttl_days)

        response = JSONResponse(status_code=200, content={"status": "ok"})
        response.set_cookie(
            key="access_token",
            value=jwt_access,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=jwt_access_ttl_minutes * 60,
        )
        response.set_cookie(
            key="refresh_token",
            value=jwt_refresh,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=jwt_refresh_ttl_days * 24 * 60 * 60,
        )

        return response

    @router.post("/logout")
    async def logout_endpoint() -> Response:
        """Clear all auth cookies and optionally revoke the Google token.

        Always returns 200 — logout is best-effort.
        """
        response = JSONResponse(status_code=200, content={"status": "ok"})
        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")
        response.delete_cookie(key="csrf_token")

        # Audit log for logout could be added here if a session is provided.
        # For now, logout is stateless and best-effort.

        return response

    if dev_login_enabled:

        @router.get("/dev-login")
        async def dev_login(
            session: AsyncSession = _session_dep,
        ) -> Response:
            """Auto-login as a dev user — no Google OAuth required.

            Creates the dev user on first use, then issues JWT cookies
            and redirects to the dashboard.  Only available when
            DEV_LOGIN_ENABLED=true.
            """
            import uuid

            dev_google_id = "dev-user-000"
            result = await session.execute(
                select(User).where(User.google_id == dev_google_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    id=uuid.uuid4(),
                    google_id=dev_google_id,
                    email="dev@example.com",
                    display_name="Dev User",
                    avatar_url=None,
                    llm_consent_given_at=datetime.now(tz=UTC),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

            jwt_access = create_access_token(str(user.id), secret_key, jwt_access_ttl_minutes)
            jwt_refresh = create_refresh_token(str(user.id), secret_key, jwt_refresh_ttl_days)
            csrf_token = generate_csrf_token()

            redirect_url = f"{frontend_url}/dashboard"
            response = RedirectResponse(url=redirect_url)
            response.set_cookie(
                key="access_token",
                value=jwt_access,
                httponly=True,
                secure=True,
                samesite="none",
                max_age=jwt_access_ttl_minutes * 60,
            )
            response.set_cookie(
                key="refresh_token",
                value=jwt_refresh,
                httponly=True,
                secure=True,
                samesite="none",
                max_age=jwt_refresh_ttl_days * 24 * 60 * 60,
            )
            response.set_cookie(
                key="csrf_token",
                value=csrf_token,
                httponly=False,
                secure=True,
                samesite="none",
                max_age=jwt_access_ttl_minutes * 60,
            )

            return response

    return router


def _clear_cookies_response(
    *,
    status_code: int,
    content: dict,
) -> JSONResponse:
    """Create a JSON response that also clears auth cookies."""
    response = JSONResponse(status_code=status_code, content=content)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    response.delete_cookie(key="csrf_token")
    return response
