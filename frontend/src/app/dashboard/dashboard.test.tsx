/**
 * Tests for the Dashboard page.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks/useDashboard", () => ({
  useDashboard: vi.fn(),
}));

import DashboardPage from "./page";
import { useDashboard } from "@/lib/hooks/useDashboard";

const mockUseDashboard = vi.mocked(useDashboard);

beforeEach(() => {
  mockUseDashboard.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DashboardPage", () => {
  it("renders a heading", () => {
    mockUseDashboard.mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
    });
    render(<DashboardPage />);
    expect(
      screen.getByRole("heading", { name: /dashboard/i }),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseDashboard.mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
    });
    render(<DashboardPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseDashboard.mockReturnValue({
      data: null,
      isLoading: false,
      error: "Failed to load",
    });
    render(<DashboardPage />);
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  it("shows dashboard content when data is loaded", () => {
    mockUseDashboard.mockReturnValue({
      data: {
        groups_count: 2,
        threads_count: 10,
        nuggets_count: 5,
        recent_threads: [
          {
            subject: "Test Thread",
            group_name: "Test Group",
            message_count: 3,
            last_activity: "2024-06-15T12:00:00+00:00",
          },
        ],
        recent_nuggets: [
          {
            content_preview: "Test nugget content",
            source_thread_subject: "Source Thread",
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    render(<DashboardPage />);
    expect(screen.getByText("Test Thread")).toBeInTheDocument();
    expect(screen.getByText("Test nugget content")).toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    mockUseDashboard.mockReturnValue({
      data: {
        groups_count: 0,
        threads_count: 0,
        nuggets_count: 0,
        recent_threads: [],
        recent_nuggets: [],
      },
      isLoading: false,
      error: null,
    });
    render(<DashboardPage />);
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(3);
  });
});
