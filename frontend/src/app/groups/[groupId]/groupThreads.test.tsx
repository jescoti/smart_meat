/**
 * Tests for the Group Threads page (thread list for a group).
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useParams: vi.fn(),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
  })),
}));

vi.mock("@/lib/hooks/useThreads", () => ({
  useThreadList: vi.fn(),
}));

import GroupThreadsPage from "./page";
import { useThreadList } from "@/lib/hooks/useThreads";
import { useParams, useRouter } from "next/navigation";

const mockUseThreadList = vi.mocked(useThreadList);
const mockUseParams = vi.mocked(useParams);
const mockUseRouter = vi.mocked(useRouter);
const mockPush = vi.fn();

beforeEach(() => {
  mockUseParams.mockReturnValue({ groupId: "group-1" });
  mockUseRouter.mockReturnValue({
    push: mockPush,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  });
  mockPush.mockClear();

  mockUseThreadList.mockReturnValue({
    threads: [],
    total: 0,
    page: 1,
    perPage: 20,
    isLoading: false,
    error: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GroupThreadsPage", () => {
  it("renders a page heading", () => {
    render(<GroupThreadsPage />);
    expect(
      screen.getByRole("heading", { name: /threads/i }),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseThreadList.mockReturnValue({
      threads: [],
      total: 0,
      page: 1,
      perPage: 20,
      isLoading: true,
      error: null,
    });

    render(<GroupThreadsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseThreadList.mockReturnValue({
      threads: [],
      total: 0,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: "Failed to load threads",
    });

    render(<GroupThreadsPage />);
    expect(screen.getByText(/failed to load threads/i)).toBeInTheDocument();
  });

  it("shows empty state when no threads", () => {
    render(<GroupThreadsPage />);
    expect(screen.getByText(/no threads/i)).toBeInTheDocument();
  });

  it("renders thread list", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Discussion about project",
          message_count: 10,
          participant_count: 4,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    expect(
      screen.getByText("Discussion about project"),
    ).toBeInTheDocument();
  });

  it("shows message count for each thread", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Discussion about project",
          message_count: 10,
          participant_count: 4,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    expect(screen.getByText(/10/)).toBeInTheDocument();
  });

  it("shows participant count for each thread", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Discussion about project",
          message_count: 10,
          participant_count: 4,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    expect(screen.getByText(/4 participants/)).toBeInTheDocument();
  });

  it("navigates to thread detail on click", async () => {
    const user = userEvent.setup();
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Discussion about project",
          message_count: 10,
          participant_count: 4,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);

    await user.click(screen.getByText("Discussion about project"));

    expect(mockPush).toHaveBeenCalledWith(
      "/groups/group-1/threads/thread-1",
    );
  });

  it("shows pagination controls", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Thread 1",
          message_count: 5,
          participant_count: 2,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 40,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    expect(screen.getByText(/next/i)).toBeInTheDocument();
  });

  it("disables previous button on first page", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Thread 1",
          message_count: 5,
          participant_count: 2,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 40,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    const prevButton = screen.getByRole("button", { name: /previous/i });
    expect(prevButton).toBeDisabled();
  });

  it("disables next button on last page", () => {
    mockUseThreadList.mockReturnValue({
      threads: [
        {
          id: "thread-1",
          subject: "Thread 1",
          message_count: 5,
          participant_count: 2,
          last_message_at: "2024-01-15T10:30:00+00:00",
          created_at: "2024-01-10T08:00:00+00:00",
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<GroupThreadsPage />);
    const nextButton = screen.getByRole("button", { name: /next/i });
    expect(nextButton).toBeDisabled();
  });
});
