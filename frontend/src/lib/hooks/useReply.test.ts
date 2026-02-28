/**
 * Tests for useReply hook.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useReply } from "./useReply";

// Mock apiFetch
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

describe("useReply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns sendReply, isLoading, and error", () => {
    const { result } = renderHook(() => useReply("thread-1"));
    expect(result.current.sendReply).toBeDefined();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("sends POST request with correct URL and body", async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: {
          id: "new-msg",
          sender_email: "user@example.com",
          body_text: "My reply",
        },
      }),
    } as Response);

    const { result } = renderHook(() => useReply("thread-1"));

    await act(async () => {
      await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(mockApiFetch).toHaveBeenCalledWith("/api/threads/thread-1/reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parent_message_id: "parent-msg-1",
        body_text: "My reply",
      }),
    });
  });

  it("sets isLoading to true while sending", async () => {
    let resolvePromise: (value: Response) => void;
    const pendingPromise = new Promise<Response>((resolve) => {
      resolvePromise = resolve;
    });
    mockApiFetch.mockReturnValueOnce(pendingPromise);

    const { result } = renderHook(() => useReply("thread-1"));

    let sendPromise: Promise<boolean>;
    act(() => {
      sendPromise = result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolvePromise!({
        ok: true,
        json: async () => ({ message: { id: "new-msg" } }),
      } as Response);
      await sendPromise!;
    });

    expect(result.current.isLoading).toBe(false);
  });

  it("returns true on success", async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: { id: "new-msg" } }),
    } as Response);

    const { result } = renderHook(() => useReply("thread-1"));

    let success: boolean = false;
    await act(async () => {
      success = await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(success).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("sets error on API failure", async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: "Failed to send" }),
    } as Response);

    const { result } = renderHook(() => useReply("thread-1"));

    let success: boolean = true;
    await act(async () => {
      success = await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(success).toBe(false);
    expect(result.current.error).toBe("Failed to send");
  });

  it("uses default error message when API response has no message field", async () => {
    mockApiFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "server_error" }),
    } as Response);

    const { result } = renderHook(() => useReply("thread-1"));

    let success: boolean = true;
    await act(async () => {
      success = await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(success).toBe(false);
    expect(result.current.error).toBe("Failed to send reply");
  });

  it("sets error on network failure", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() => useReply("thread-1"));

    let success: boolean = true;
    await act(async () => {
      success = await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(success).toBe(false);
    expect(result.current.error).toBe("Network error");
  });

  it("clears previous error on new send", async () => {
    // First call fails
    mockApiFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: "First error" }),
    } as Response);

    const { result } = renderHook(() => useReply("thread-1"));

    await act(async () => {
      await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(result.current.error).toBe("First error");

    // Second call succeeds
    mockApiFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: { id: "new-msg" } }),
    } as Response);

    await act(async () => {
      await result.current.sendReply("parent-msg-1", "My reply");
    });

    expect(result.current.error).toBeNull();
  });
});
