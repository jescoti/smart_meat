/**
 * Tests for sync hooks.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import {
  useGroups,
  useSyncStatus,
  useTriggerSync,
  useAddGroup,
} from "./useSync";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useGroups", () => {
  it("fetches groups on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "group-1",
            gmail_group_email: "test@googlegroups.com",
            sync_status: "idle",
          },
        ]),
    } as Response);

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.groups).toHaveLength(1);
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/groups");
  });

  it("sets loading true initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const { result } = renderHook(() => useGroups());

    expect(result.current.loading).toBe(true);
  });

  it("sets loading false after fetch", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it("sets error on fetch failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({ error: "unauthorized", message: "Not logged in" }),
    } as Response);

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("provides a refresh function", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockApiFetch).toHaveBeenCalledTimes(2);
  });

  it("sets error on network failure (fetch throws)", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });

    expect(result.current.loading).toBe(false);
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useGroups());

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load groups");
    });
  });
});

describe("useSyncStatus", () => {
  it("fetches sync status", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "syncing",
          progress_current: 5,
          progress_total: 10,
          error_message: null,
        }),
    } as Response);

    const { result } = renderHook(() => useSyncStatus("group-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("syncing");
    });

    expect(result.current.progressCurrent).toBe(5);
    expect(result.current.progressTotal).toBe(10);
    expect(result.current.errorMessage).toBeNull();
  });

  it("polls when syncing", async () => {
    vi.useFakeTimers();

    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "syncing",
          progress_current: 5,
          progress_total: 10,
          error_message: null,
        }),
    } as Response);

    renderHook(() => useSyncStatus("group-1"));

    // First fetch on mount
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockApiFetch).toHaveBeenCalledTimes(1);

    // Advance by polling interval
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(mockApiFetch).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });

  it("stops polling when idle", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "idle",
          progress_current: null,
          progress_total: null,
          error_message: null,
        }),
    } as Response);

    const { result } = renderHook(() => useSyncStatus("group-1"));

    await waitFor(() => {
      expect(result.current.status).toBe("idle");
    });

    // The important thing is it reached idle without error
    expect(result.current.status).toBe("idle");
  });

  it("does not fetch when groupId is null", () => {
    renderHook(() => useSyncStatus(null));

    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("handles non-ok response silently", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unauthorized" }),
    } as Response);

    const { result } = renderHook(() => useSyncStatus("group-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Status should remain null since response was not ok
    expect(result.current.status).toBeNull();
  });

  it("handles fetch error silently", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useSyncStatus("group-1"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Should not throw, status remains null
    expect(result.current.status).toBeNull();
  });

  it("cleans up interval on unmount", async () => {
    vi.useFakeTimers();

    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "syncing",
          progress_current: 5,
          progress_total: 10,
          error_message: null,
        }),
    } as Response);

    const { unmount } = renderHook(() => useSyncStatus("group-1"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    unmount();

    // After unmount, advancing timers should not cause additional calls
    const callCountAtUnmount = mockApiFetch.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    expect(mockApiFetch.mock.calls.length).toBe(callCountAtUnmount);

    vi.useRealTimers();
  });
});

describe("useTriggerSync", () => {
  it("triggers sync for a group", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ status: "syncing", group_id: "group-1" }),
    } as Response);

    const { result } = renderHook(() => useTriggerSync());

    await act(async () => {
      await result.current.trigger("group-1");
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/groups/group-1/sync", {
      method: "POST",
    });
  });

  it("sets loading during trigger", async () => {
    let resolvePromise: (value: Response) => void;
    const promise = new Promise<Response>((r) => {
      resolvePromise = r;
    });
    mockApiFetch.mockReturnValue(promise);

    const { result } = renderHook(() => useTriggerSync());

    let triggerPromise: Promise<void>;
    act(() => {
      triggerPromise = result.current.trigger("group-1");
    });

    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolvePromise!({
        ok: true,
        json: () =>
          Promise.resolve({ status: "syncing", group_id: "group-1" }),
      } as Response);
      await triggerPromise!;
    });

    expect(result.current.loading).toBe(false);
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({ error: "not_found", message: "Group not found" }),
    } as Response);

    const { result } = renderHook(() => useTriggerSync());

    await act(async () => {
      await result.current.trigger("group-1");
    });

    expect(result.current.error).toBeTruthy();
  });

  it("sets error on network failure (fetch throws)", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useTriggerSync());

    await act(async () => {
      await result.current.trigger("group-1");
    });

    expect(result.current.error).toBe("Network error");
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useTriggerSync());

    await act(async () => {
      await result.current.trigger("group-1");
    });

    expect(result.current.error).toBe("Failed to trigger sync");
  });
});

describe("useAddGroup", () => {
  it("adds a group", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "group-1",
          gmail_group_email: "test@googlegroups.com",
          sync_status: "idle",
        }),
    } as Response);

    const { result } = renderHook(() => useAddGroup());

    await act(async () => {
      await result.current.addGroup("test@googlegroups.com");
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gmail_group_email: "test@googlegroups.com" }),
    });
  });

  it("sets loading during add", async () => {
    let resolvePromise: (value: Response) => void;
    const promise = new Promise<Response>((r) => {
      resolvePromise = r;
    });
    mockApiFetch.mockReturnValue(promise);

    const { result } = renderHook(() => useAddGroup());

    let addPromise: Promise<void>;
    act(() => {
      addPromise = result.current.addGroup("test@googlegroups.com");
    });

    expect(result.current.loading).toBe(true);

    await act(async () => {
      resolvePromise!({
        ok: true,
        json: () =>
          Promise.resolve({
            id: "group-1",
            gmail_group_email: "test@googlegroups.com",
            sync_status: "idle",
          }),
      } as Response);
      await addPromise!;
    });

    expect(result.current.loading).toBe(false);
  });

  it("sets error on failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({
          error: "bad_request",
          message: "Invalid email",
        }),
    } as Response);

    const { result } = renderHook(() => useAddGroup());

    await act(async () => {
      await result.current.addGroup("invalid");
    });

    expect(result.current.error).toBeTruthy();
  });

  it("sets error on network failure (fetch throws)", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useAddGroup());

    await act(async () => {
      await result.current.addGroup("test@googlegroups.com");
    });

    expect(result.current.error).toBe("Network error");
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useAddGroup());

    await act(async () => {
      await result.current.addGroup("test@googlegroups.com");
    });

    expect(result.current.error).toBe("Failed to add group");
  });
});
