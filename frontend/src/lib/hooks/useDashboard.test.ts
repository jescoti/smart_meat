/**
 * Tests for the useDashboard hook.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { useDashboard } from "./useDashboard";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

const MOCK_SUMMARY = {
  groups_count: 3,
  threads_count: 25,
  nuggets_count: 12,
  recent_threads: [
    {
      subject: "Weekly Meeting Notes",
      group_name: "Engineering",
      message_count: 10,
      last_activity: "2024-06-15T12:00:00+00:00",
    },
  ],
  recent_nuggets: [
    {
      content_preview: "Testing best practices include writing tests first.",
      source_thread_subject: "Testing Discussion",
    },
  ],
};

describe("useDashboard", () => {
  it("fetches dashboard summary on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SUMMARY),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/dashboard/summary");
  });

  it("returns data on success", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SUMMARY),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    await waitFor(() => {
      expect(result.current.data).not.toBeNull();
    });

    expect(result.current.data?.groups_count).toBe(3);
    expect(result.current.data?.threads_count).toBe(25);
    expect(result.current.data?.nuggets_count).toBe(12);
    expect(result.current.data?.recent_threads).toHaveLength(1);
    expect(result.current.data?.recent_threads[0].subject).toBe(
      "Weekly Meeting Notes",
    );
    expect(result.current.data?.recent_nuggets).toHaveLength(1);
    expect(result.current.data?.recent_nuggets[0].content_preview).toBe(
      "Testing best practices include writing tests first.",
    );
  });

  it("sets loading true during fetch", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SUMMARY),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    expect(result.current.isLoading).toBe(true);
  });

  it("sets error on API error response", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: "unauthorized",
          message: "Missing user ID",
        }),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });

    expect(result.current.error).toBe("Missing user ID");
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useDashboard());

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load dashboard");
    });
  });

  it("returns null data initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SUMMARY),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    expect(result.current.data).toBeNull();
  });

  it("returns null error initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_SUMMARY),
    } as Response);

    const { result } = renderHook(() => useDashboard());

    expect(result.current.error).toBeNull();
  });
});
