/**
 * Tests for the Search page.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/hooks/useSearch", () => ({
  useSearch: vi.fn(),
}));

import SearchPage from "./page";
import { useSearch } from "@/lib/hooks/useSearch";

const mockUseSearch = vi.mocked(useSearch);

beforeEach(() => {
  mockUseSearch.mockReturnValue({
    results: [],
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

describe("SearchPage", () => {
  it("renders a page heading", () => {
    render(<SearchPage />);

    expect(
      screen.getByRole("heading", { name: /search/i }),
    ).toBeInTheDocument();
  });

  it("renders a search input", () => {
    render(<SearchPage />);

    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseSearch.mockReturnValue({
      results: [],
      total: 0,
      page: 1,
      perPage: 20,
      isLoading: true,
      error: null,
    });

    render(<SearchPage />);

    expect(screen.getByText(/searching/i)).toBeInTheDocument();
  });

  it("shows empty state when no results and query submitted", async () => {
    const user = userEvent.setup();
    mockUseSearch.mockReturnValue({
      results: [],
      total: 0,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<SearchPage />);

    // Type a query and submit to trigger searched state
    const input = screen.getByPlaceholderText(/search/i);
    await user.type(input, "nonexistent");
    const button = screen.getByRole("button", { name: /search/i });
    await user.click(button);

    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  it("shows search results", () => {
    mockUseSearch.mockReturnValue({
      results: [
        {
          message_id: "msg-1",
          subject: "Meeting Notes",
          sender_name: "Alice",
          sender_email: "alice@example.com",
          gmail_date: "2024-01-12T09:00:00+00:00",
          snippet: "Notes from meeting...",
          group_id: "group-1",
          thread_id: "thread-1",
          rank: 0.75,
        },
      ],
      total: 1,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<SearchPage />);

    expect(screen.getByText("Meeting Notes")).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseSearch.mockReturnValue({
      results: [],
      total: 0,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: "Search failed",
    });

    render(<SearchPage />);

    expect(screen.getByText(/search failed/i)).toBeInTheDocument();
  });

  it("shows pagination when there are multiple pages", () => {
    mockUseSearch.mockReturnValue({
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
      total: 50,
      page: 1,
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<SearchPage />);

    expect(screen.getByText(/page 1/i)).toBeInTheDocument();
  });

  it("does not show pagination when results fit on one page", () => {
    mockUseSearch.mockReturnValue({
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
      perPage: 20,
      isLoading: false,
      error: null,
    });

    render(<SearchPage />);

    expect(screen.queryByText(/page 1/i)).not.toBeInTheDocument();
  });

  it("renders filter controls", () => {
    render(<SearchPage />);

    expect(screen.getByLabelText(/sender/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/to/i)).toBeInTheDocument();
  });
});
