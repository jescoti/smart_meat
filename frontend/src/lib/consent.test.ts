/**
 * Tests for consent utility functions.
 *
 * TDD RED phase -- these tests are written before the implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Mock the api module before importing consent utilities
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { getConsentStatus, grantConsent, revokeConsent } from "./consent";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getConsentStatus", () => {
  it("calls GET /api/consent", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ consented: false, consented_at: null }),
        { status: 200 },
      ),
    );

    await getConsentStatus();
    expect(mockApiFetch).toHaveBeenCalledWith("/api/consent");
  });

  it("returns consent status when not consented", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ consented: false, consented_at: null }),
        { status: 200 },
      ),
    );

    const result = await getConsentStatus();
    expect(result).toEqual({ consented: false, consented_at: null });
  });

  it("returns consent status when consented", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          consented: true,
          consented_at: "2024-06-15T12:00:00+00:00",
        }),
        { status: 200 },
      ),
    );

    const result = await getConsentStatus();
    expect(result).toEqual({
      consented: true,
      consented_at: "2024-06-15T12:00:00+00:00",
    });
  });

  it("throws on non-200 response", async () => {
    mockApiFetch.mockResolvedValue(new Response("error", { status: 500 }));

    await expect(getConsentStatus()).rejects.toThrow();
  });
});

describe("grantConsent", () => {
  it("calls POST /api/consent", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    await grantConsent();
    expect(mockApiFetch).toHaveBeenCalledWith("/api/consent", {
      method: "POST",
    });
  });

  it("returns true on success", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    const result = await grantConsent();
    expect(result).toBe(true);
  });

  it("returns false on failure", async () => {
    mockApiFetch.mockResolvedValue(new Response("error", { status: 500 }));

    const result = await grantConsent();
    expect(result).toBe(false);
  });

  it("returns false on network error", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const result = await grantConsent();
    expect(result).toBe(false);
  });
});

describe("revokeConsent", () => {
  it("calls DELETE /api/consent", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    await revokeConsent();
    expect(mockApiFetch).toHaveBeenCalledWith("/api/consent", {
      method: "DELETE",
    });
  });

  it("returns true on success", async () => {
    mockApiFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    const result = await revokeConsent();
    expect(result).toBe(true);
  });

  it("returns false on failure", async () => {
    mockApiFetch.mockResolvedValue(new Response("error", { status: 500 }));

    const result = await revokeConsent();
    expect(result).toBe(false);
  });

  it("returns false on network error", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const result = await revokeConsent();
    expect(result).toBe(false);
  });
});
