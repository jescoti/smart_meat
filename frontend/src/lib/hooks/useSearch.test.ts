/**
 * Tests for the useSearch hook.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { useSearch } from "./useSearch";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useSearch", () => {
  it("does not fetch when query is empty", () => {
    renderHook(() => useSearch("", {}));

    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("does not fetch when query is whitespace", () => {
    renderHook(() => useSearch("   ", {}));

    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("fetches when query is non-empty", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: [],
          total: 0,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result } = renderHook(() => useSearch("test query", {}));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/search?q=test+query&page=1&per_page=20",
    );
  });

  it("returns results on success", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: [
            {
              message_id: "msg-1",
              subject: "Meeting Notes",
              sender_name: "Alice",
              sender_email: "alice@example.com",
              gmail_date: "2024-01-12T09:00:00+00:00",
              snippet: "Notes from weekly...",
              group_id: "group-1",
              thread_id: "thread-1",
              rank: 0.75,
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result } = renderHook(() => useSearch("meeting", {}));

    await waitFor(() => {
      expect(result.current.results).toHaveLength(1);
    });

    expect(result.current.results[0].subject).toBe("Meeting Notes");
    expect(result.current.total).toBe(1);
    expect(result.current.page).toBe(1);
    expect(result.current.perPage).toBe(20);
  });

  it("sets loading true during fetch", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ results: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useSearch("test", {}));

    expect(result.current.isLoading).toBe(true);
  });

  it("sets loading false when query is empty", () => {
    const { result } = renderHook(() => useSearch("", {}));

    expect(result.current.isLoading).toBe(false);
  });

  it("sets error on fetch failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: "bad_request",
          message: "Search query is required",
        }),
    } as Response);

    const { result } = renderHook(() => useSearch("test", {}));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useSearch("test", {}));

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useSearch("test", {}));

    await waitFor(() => {
      expect(result.current.error).toBe("Search failed");
    });
  });

  it("passes filter parameters in URL", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ results: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() =>
      useSearch("test", {
        groupId: "group-123",
        sender: "alice@example.com",
        dateFrom: "2024-01-01",
        dateTo: "2024-12-31",
      }),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const calledUrl = mockApiFetch.mock.calls[0][0];
    expect(calledUrl).toContain("group_id=group-123");
    expect(calledUrl).toContain("sender=alice%40example.com");
    expect(calledUrl).toContain("date_from=2024-01-01");
    expect(calledUrl).toContain("date_to=2024-12-31");
  });

  it("passes custom page and per_page", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ results: [], total: 50, page: 3, per_page: 10 }),
    } as Response);

    const { result } = renderHook(() =>
      useSearch("test", {}, 3, 10),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      expect.stringContaining("page=3&per_page=10"),
    );
  });

  it("returns empty results initially", () => {
    const { result } = renderHook(() => useSearch("", {}));

    expect(result.current.results).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.error).toBeNull();
  });

  it("clears results when query becomes empty", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          results: [
            {
              message_id: "msg-1",
              subject: "Test",
              sender_name: "Alice",
              sender_email: "alice@example.com",
              gmail_date: "2024-01-12T09:00:00+00:00",
              snippet: "snippet",
              group_id: "group-1",
              thread_id: null,
              rank: 0.5,
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result, rerender } = renderHook(
      ({ query }: { query: string }) => useSearch(query, {}),
      { initialProps: { query: "test" } },
    );

    await waitFor(() => {
      expect(result.current.results).toHaveLength(1);
    });

    rerender({ query: "" });

    expect(result.current.results).toEqual([]);
    expect(result.current.total).toBe(0);
  });
});
