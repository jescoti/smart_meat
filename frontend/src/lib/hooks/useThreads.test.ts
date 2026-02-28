/**
 * Tests for thread hooks — useThreadList and useThreadDetail.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { useThreadList, useThreadDetail } from "./useThreads";
import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useThreadList", () => {
  it("fetches threads on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          threads: [
            {
              id: "thread-1",
              subject: "Test Thread",
              message_count: 5,
              participant_count: 3,
              last_message_at: "2024-01-15T10:30:00+00:00",
              created_at: "2024-01-10T08:00:00+00:00",
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.threads).toHaveLength(1);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/groups/group-1/threads?page=1&per_page=20",
    );
  });

  it("sets loading true initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ threads: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    expect(result.current.isLoading).toBe(true);
  });

  it("sets loading false after fetch", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ threads: [], total: 0, page: 1, per_page: 20 }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns thread data", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          threads: [
            {
              id: "thread-1",
              subject: "Test Thread",
              message_count: 5,
              participant_count: 3,
              last_message_at: "2024-01-15T10:30:00+00:00",
              created_at: "2024-01-10T08:00:00+00:00",
            },
          ],
          total: 1,
          page: 1,
          per_page: 20,
        }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.threads).toHaveLength(1);
    });

    expect(result.current.total).toBe(1);
    expect(result.current.page).toBe(1);
    expect(result.current.perPage).toBe(20);
  });

  it("passes custom page and perPage", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ threads: [], total: 50, page: 3, per_page: 10 }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1", 3, 10));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/groups/group-1/threads?page=3&per_page=10",
    );
  });

  it("sets error on fetch failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({ error: "not_found", message: "Group not found" }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useThreadList("group-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load threads");
    });
  });
});

describe("useThreadDetail", () => {
  it("fetches thread detail on mount", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          thread: {
            id: "thread-1",
            subject: "Test Thread",
            message_count: 5,
            participant_count: 3,
            last_message_at: "2024-01-15T10:30:00+00:00",
            created_at: "2024-01-10T08:00:00+00:00",
          },
          messages: [
            {
              id: "msg-1",
              sender_email: "alice@example.com",
              sender_name: "Alice",
              subject: "Test Subject",
              body_text: "Hello",
              body_html: null,
              gmail_date: "2024-01-12T09:00:00+00:00",
              depth: 0,
              is_ghost: false,
              parent_message_id: null,
            },
          ],
        }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.thread).toBeTruthy();
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/threads/thread-1");
  });

  it("sets loading true initially", () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ thread: null, messages: [] }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    expect(result.current.isLoading).toBe(true);
  });

  it("sets loading false after fetch", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          thread: {
            id: "thread-1",
            subject: "Test",
            message_count: 0,
            participant_count: 0,
            last_message_at: null,
            created_at: "2024-01-10T08:00:00+00:00",
          },
          messages: [],
        }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it("returns thread and messages", async () => {
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          thread: {
            id: "thread-1",
            subject: "Test Thread",
            message_count: 2,
            participant_count: 2,
            last_message_at: "2024-01-15T10:30:00+00:00",
            created_at: "2024-01-10T08:00:00+00:00",
          },
          messages: [
            {
              id: "msg-1",
              sender_email: "alice@example.com",
              sender_name: "Alice",
              subject: "Test Subject",
              body_text: "Hello",
              body_html: null,
              gmail_date: "2024-01-12T09:00:00+00:00",
              depth: 0,
              is_ghost: false,
              parent_message_id: null,
            },
            {
              id: "msg-2",
              sender_email: "bob@example.com",
              sender_name: "Bob",
              subject: "Re: Test Subject",
              body_text: "Reply",
              body_html: null,
              gmail_date: "2024-01-12T10:00:00+00:00",
              depth: 1,
              is_ghost: false,
              parent_message_id: "msg-1",
            },
          ],
        }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });

    expect(result.current.thread?.subject).toBe("Test Thread");
  });

  it("sets error on fetch failure", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () =>
        Promise.resolve({ error: "not_found", message: "Thread not found" }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
    });
  });

  it("uses fallback error message when response has no message", async () => {
    mockApiFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ error: "unknown" }),
    } as Response);

    const { result } = renderHook(() => useThreadDetail("thread-1"));

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to load thread");
    });
  });

  it("does not fetch when threadId is null", () => {
    const { result } = renderHook(() => useThreadDetail(null));

    expect(mockApiFetch).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });
});
