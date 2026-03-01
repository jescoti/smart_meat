/**
 * Authentication utilities for the frontend.
 *
 * Provides functions to interact with the backend auth endpoints:
 * - getLoginUrl: fetches the Google OAuth authorization URL
 * - refreshToken: refreshes the JWT access token
 * - logout: clears the auth session
 * - fetchCurrentUser: checks auth state and returns user profile
 */

import type { AuthUser } from "@/stores/authStore";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * Fetch the Google OAuth login URL from the backend.
 *
 * @returns The authorization URL to redirect the user to.
 * @throws If the backend returns a non-200 response.
 */
export async function getLoginUrl(): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/auth/login`, {
    credentials: "include",
  });

  if (!resp.ok) {
    throw new Error(`Failed to get login URL: ${resp.status}`);
  }

  const data = await resp.json();
  return data.url;
}

/**
 * Call the backend refresh endpoint to obtain new JWT tokens.
 *
 * @returns `true` if the refresh succeeded, `false` otherwise.
 */
export async function refreshToken(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    return resp.ok;
  } catch {
    return false;
  }
}

/**
 * Call the backend logout endpoint. Best-effort — never throws.
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Best-effort logout — ignore errors
  }
}

/**
 * Fetch the current user's profile from /api/auth/me.
 *
 * If the initial request returns 401, attempts a token refresh and retries once.
 * Returns null if the user is not authenticated or on any error.
 */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    const resp = await fetch(`${API_BASE}/api/auth/me`, {
      credentials: "include",
    });

    if (resp.ok) {
      return await resp.json();
    }

    if (resp.status === 401) {
      const refreshed = await refreshToken();
      if (!refreshed) {
        return null;
      }

      const retryResp = await fetch(`${API_BASE}/api/auth/me`, {
        credentials: "include",
      });

      if (retryResp.ok) {
        return await retryResp.json();
      }
    }

    return null;
  } catch {
    return null;
  }
}
