/**
 * Tests for the Thread Detail page.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
}));

vi.mock("@/lib/hooks/useThreads", () => ({
  useThreadDetail: vi.fn(),
}));

import ThreadDetailPage from "./page";
import { useThreadDetail } from "@/lib/hooks/useThreads";
import { useParams } from "next/navigation";

const mockUseThreadDetail = vi.mocked(useThreadDetail);
const mockUseParams = vi.mocked(useParams);

beforeEach(() => {
  mockUseParams.mockReturnValue({ threadId: "thread-1", groupId: "group-1" });

  mockUseThreadDetail.mockReturnValue({
    thread: null,
    messages: [],
    isLoading: false,
    error: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ThreadDetailPage", () => {
  it("renders thread subject as heading", () => {
    mockUseThreadDetail.mockReturnValue({
      thread: {
        id: "thread-1",
        subject: "Important Discussion",
        message_count: 5,
        participant_count: 3,
        last_message_at: "2024-01-15T10:30:00+00:00",
        created_at: "2024-01-10T08:00:00+00:00",
      },
      messages: [],
      isLoading: false,
      error: null,
    });

    render(<ThreadDetailPage />);
    expect(
      screen.getByRole("heading", { name: /important discussion/i }),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseThreadDetail.mockReturnValue({
      thread: null,
      messages: [],
      isLoading: true,
      error: null,
    });

    render(<ThreadDetailPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseThreadDetail.mockReturnValue({
      thread: null,
      messages: [],
      isLoading: false,
      error: "Thread not found",
    });

    render(<ThreadDetailPage />);
    expect(screen.getByText(/thread not found/i)).toBeInTheDocument();
  });

  it("renders ThreadViewer with messages", () => {
    mockUseThreadDetail.mockReturnValue({
      thread: {
        id: "thread-1",
        subject: "Test Thread",
        message_count: 1,
        participant_count: 1,
        last_message_at: "2024-01-15T10:30:00+00:00",
        created_at: "2024-01-10T08:00:00+00:00",
      },
      messages: [
        {
          id: "msg-1",
          sender_email: "alice@example.com",
          sender_name: "Alice",
          subject: "Test Thread",
          body_text: "Hello world",
          body_html: null,
          gmail_date: "2024-01-12T09:00:00+00:00",
          depth: 0,
          is_ghost: false,
          parent_message_id: null,
        },
      ],
      isLoading: false,
      error: null,
    });

    render(<ThreadDetailPage />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("passes threadId from params to useThreadDetail", () => {
    render(<ThreadDetailPage />);
    expect(mockUseThreadDetail).toHaveBeenCalledWith("thread-1");
  });
});
