/**
 * Tests for knowledge hooks -- useNuggets, useNuggetDetail, mutations.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import {
  useNuggets,
  useNuggetDetail,
  useCreateNugget,
  useAcceptNugget,
  useRejectNugget,
} from "./useKnowledge";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// useNuggets
// ---------------------------------------------------------------------------

describe("useNuggets", () => {
  it("fetches nuggets on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          nuggets: [
            {
              id: "nugget-1",
              title: "Test Nugget",
              content: "Content",
              tags: ["test"],
              source_type: "manual",
              status: "accepted",
              created_at: "2024-06-15T12:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.nuggets).toHaveLength(1);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/knowledge/nuggets?group_id=group-1&page=1&per_page=20",
    );
  });

  it("sets loading true initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ nuggets: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));
    expect(result.current.isLoading).toBe(true);
  });

  it("sets loading false after fetch", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ nuggets: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("filters by status", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ nuggets: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() =>
      useNuggets("group-1", "suggested", 1),
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/knowledge/nuggets?group_id=group-1&status=suggested&page=1&per_page=20",
    );
  });

  it("sets error on fetch failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Server error" }),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("returns total count", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ nuggets: [], total: 42, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.total).toBe(42);
    });
  });

  it("uses fallback error message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useNuggets("group-1", null, 1));

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load nuggets");
    });
  });
});

// ---------------------------------------------------------------------------
// useNuggetDetail
// ---------------------------------------------------------------------------

describe("useNuggetDetail", () => {
  it("fetches nugget detail on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "nugget-1",
          title: "Test Nugget",
          content: "Content",
          tags: ["test"],
          source_type: "manual",
          status: "accepted",
          created_at: "2024-06-15T12:00:00Z",
        }),
    } as Response);

    const { result } = renderHook(() => useNuggetDetail("nugget-1"));

    await waitFor(() => {
      expect(result.current.nugget).toBeTruthy();
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/knowledge/nuggets/nugget-1",
    );
  });

  it("does not fetch when nuggetId is null", () => {
    const { result } = renderHook(() => useNuggetDetail(null));
    expect(mockApiFetch).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Not found" }),
    } as Response);

    const { result } = renderHook(() => useNuggetDetail("nugget-1"));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useNuggetDetail("nugget-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("uses fallback error message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useNuggetDetail("nugget-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load nugget");
    });
  });
});

// ---------------------------------------------------------------------------
// useCreateNugget
// ---------------------------------------------------------------------------

describe("useCreateNugget", () => {
  it("creates a nugget via POST", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "nugget-new",
          title: "New Note",
          content: "New content",
          tags: [],
          source_type: "manual",
          status: "accepted",
        }),
    } as Response);

    const { result } = renderHook(() => useCreateNugget());

    await act(async () => {
      await result.current.createNugget({
        group_id: "group-1",
        title: "New Note",
        content: "New content",
        tags: [],
      });
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/knowledge/nuggets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: "group-1",
        title: "New Note",
        content: "New content",
        tags: [],
      }),
    });
  });

  it("sets loading during mutation", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "nugget-new" }),
    } as Response);

    const { result } = renderHook(() => useCreateNugget());
    expect(result.current.isLoading).toBe(false);
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Validation failed" }),
    } as Response);

    const { result } = renderHook(() => useCreateNugget());

    await act(async () => {
      await result.current.createNugget({
        group_id: "group-1",
        title: "Note",
        content: "Content",
        tags: [],
      });
    });

    expect(result.current.error).toBeTruthy();
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useCreateNugget());

    await act(async () => {
      await result.current.createNugget({
        group_id: "group-1",
        title: "Note",
        content: "Content",
        tags: [],
      });
    });

    expect(result.current.error).toBe("Network error");
  });

  it("uses fallback error message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useCreateNugget());

    await act(async () => {
      await result.current.createNugget({
        group_id: "group-1",
        title: "Note",
        content: "Content",
        tags: [],
      });
    });

    expect(result.current.error).toBe("Failed to create nugget");
  });
});

// ---------------------------------------------------------------------------
// useAcceptNugget
// ---------------------------------------------------------------------------

describe("useAcceptNugget", () => {
  it("accepts a nugget via POST", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ id: "nugget-1", status: "accepted" }),
    } as Response);

    const { result } = renderHook(() => useAcceptNugget());

    await act(async () => {
      await result.current.acceptNugget("nugget-1");
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/knowledge/nuggets/nugget-1/accept",
      { method: "POST" },
    );
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Not found" }),
    } as Response);

    const { result } = renderHook(() => useAcceptNugget());

    await act(async () => {
      await result.current.acceptNugget("nugget-1");
    });

    expect(result.current.error).toBeTruthy();
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useAcceptNugget());

    await act(async () => {
      await result.current.acceptNugget("nugget-1");
    });

    expect(result.current.error).toBe("Network error");
  });

  it("uses fallback error message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useAcceptNugget());

    await act(async () => {
      await result.current.acceptNugget("nugget-1");
    });

    expect(result.current.error).toBe("Failed to accept nugget");
  });
});

// ---------------------------------------------------------------------------
// useRejectNugget
// ---------------------------------------------------------------------------

describe("useRejectNugget", () => {
  it("rejects a nugget via POST", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ id: "nugget-1", status: "rejected" }),
    } as Response);

    const { result } = renderHook(() => useRejectNugget());

    await act(async () => {
      await result.current.rejectNugget("nugget-1");
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/knowledge/nuggets/nugget-1/reject",
      { method: "POST" },
    );
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Not found" }),
    } as Response);

    const { result } = renderHook(() => useRejectNugget());

    await act(async () => {
      await result.current.rejectNugget("nugget-1");
    });

    expect(result.current.error).toBeTruthy();
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useRejectNugget());

    await act(async () => {
      await result.current.rejectNugget("nugget-1");
    });

    expect(result.current.error).toBe("Network error");
  });

  it("uses fallback error message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response);

    const { result } = renderHook(() => useRejectNugget());

    await act(async () => {
      await result.current.rejectNugget("nugget-1");
    });

    expect(result.current.error).toBe("Failed to reject nugget");
  });
});
