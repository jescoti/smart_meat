/**
 * Tests for auth utilities — getLoginUrl, refreshToken, logout.
 *
 * TDD RED phase — these tests are written before the implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { getLoginUrl, refreshToken, logout } from "./auth";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockClear();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getLoginUrl", () => {
  it("calls the backend login endpoint", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ url: "https://accounts.google.com/o/oauth2/v2/auth?..." }),
        { status: 200 },
      ),
    );

    await getLoginUrl();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/login"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns the authorization URL string", async () => {
    const expectedUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test";
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ url: expectedUrl }), { status: 200 }),
    );

    const url = await getLoginUrl();
    expect(url).toBe(expectedUrl);
  });

  it("throws on non-200 response", async () => {
    mockFetch.mockResolvedValue(new Response("error", { status: 500 }));

    await expect(getLoginUrl()).rejects.toThrow();
  });
});

describe("refreshToken", () => {
  it("calls the backend refresh endpoint with POST", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    await refreshToken();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/refresh"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });

  it("returns true on success", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    const result = await refreshToken();
    expect(result).toBe(true);
  });

  it("returns false on 401", async () => {
    mockFetch.mockResolvedValue(new Response("unauthorized", { status: 401 }));

    const result = await refreshToken();
    expect(result).toBe(false);
  });

  it("returns false on network error", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const result = await refreshToken();
    expect(result).toBe(false);
  });
});

describe("logout", () => {
  it("calls the backend logout endpoint with POST", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    await logout();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/logout"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });

  it("resolves without error on success", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));

    await expect(logout()).resolves.toBeUndefined();
  });

  it("resolves without error even on failure", async () => {
    mockFetch.mockResolvedValue(new Response("error", { status: 500 }));

    // Logout should not throw — best-effort
    await expect(logout()).resolves.toBeUndefined();
  });
});
