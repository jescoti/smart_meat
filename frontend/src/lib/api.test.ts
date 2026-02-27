/**
 * Tests for the API fetch wrapper with CSRF support.
 *
 * TDD RED phase — these tests are written before the implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiFetch } from "./api";

// Mock global fetch
const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockClear();
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), { status: 200 }),
  );
  // Clear the csrf_token cookie by setting it to expired
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

describe("apiFetch", () => {
  describe("base URL", () => {
    it("prepends the API base URL to relative paths", async () => {
      await apiFetch("/api/data");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/data"),
        expect.any(Object),
      );
    });

    it("uses NEXT_PUBLIC_API_URL env var as base", async () => {
      vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com");
      await apiFetch("/api/data");
      expect(mockFetch).toHaveBeenCalledWith(
        "https://api.example.com/api/data",
        expect.any(Object),
      );
      vi.unstubAllEnvs();
    });

    it("defaults to empty string when env var is not set", async () => {
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");
      await apiFetch("/api/data");
      expect(mockFetch).toHaveBeenCalledWith("/api/data", expect.any(Object));
      vi.unstubAllEnvs();
    });
  });

  describe("CSRF token for mutating requests", () => {
    it("adds X-CSRF-Token header on POST requests", async () => {
      document.cookie = "csrf_token=my-csrf-value; path=/";
      await apiFetch("/api/data", { method: "POST" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("my-csrf-value");
    });

    it("adds X-CSRF-Token header on PUT requests", async () => {
      document.cookie = "csrf_token=my-csrf-value; path=/";
      await apiFetch("/api/data", { method: "PUT" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("my-csrf-value");
    });

    it("adds X-CSRF-Token header on DELETE requests", async () => {
      document.cookie = "csrf_token=my-csrf-value; path=/";
      await apiFetch("/api/data", { method: "DELETE" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("my-csrf-value");
    });

    it("adds X-CSRF-Token header on PATCH requests", async () => {
      document.cookie = "csrf_token=my-csrf-value; path=/";
      await apiFetch("/api/data", { method: "PATCH" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("my-csrf-value");
    });

    it("does NOT add X-CSRF-Token header on GET requests", async () => {
      document.cookie = "csrf_token=my-csrf-value; path=/";
      await apiFetch("/api/data");
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBeNull();
    });

    it("does NOT add X-CSRF-Token header when no cookie present", async () => {
      await apiFetch("/api/data", { method: "POST" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBeNull();
    });
  });

  describe("credentials", () => {
    it("includes credentials by default", async () => {
      await apiFetch("/api/data");
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(options.credentials).toBe("include");
    });
  });

  describe("custom options", () => {
    it("merges custom headers", async () => {
      await apiFetch("/api/data", {
        headers: { "Content-Type": "application/json" },
      });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("Content-Type")).toBe("application/json");
    });

    it("passes through body", async () => {
      document.cookie = "csrf_token=tok; path=/";
      const body = JSON.stringify({ name: "test" });
      await apiFetch("/api/data", { method: "POST", body });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      expect(options.body).toBe(body);
    });

    it("returns the fetch Response", async () => {
      const resp = await apiFetch("/api/data");
      expect(resp).toBeInstanceOf(Response);
    });
  });

  describe("method case insensitivity", () => {
    it("handles lowercase post method", async () => {
      document.cookie = "csrf_token=token-val; path=/";
      await apiFetch("/api/data", { method: "post" });
      const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("token-val");
    });
  });
});
