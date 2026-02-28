/**
 * Tests for the Suggestions page (pending nuggets).
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks/useKnowledge", () => ({
  useNuggets: vi.fn(),
  useAcceptNugget: vi.fn(),
  useRejectNugget: vi.fn(),
}));

import SuggestionsPage from "./page";
import {
  useNuggets,
  useAcceptNugget,
  useRejectNugget,
} from "@/lib/hooks/useKnowledge";

const mockUseNuggets = vi.mocked(useNuggets);
const mockUseAcceptNugget = vi.mocked(useAcceptNugget);
const mockUseRejectNugget = vi.mocked(useRejectNugget);

beforeEach(() => {
  mockUseNuggets.mockClear();
  mockUseAcceptNugget.mockClear();
  mockUseRejectNugget.mockClear();

  mockUseAcceptNugget.mockReturnValue({
    acceptNugget: vi.fn(),
    isLoading: false,
    error: null,
  });
  mockUseRejectNugget.mockReturnValue({
    rejectNugget: vi.fn(),
    isLoading: false,
    error: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SuggestionsPage", () => {
  it("renders a heading", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: null,
    });
    render(<SuggestionsPage />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: true,
      error: null,
    });
    render(<SuggestionsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: "Failed to load",
    });
    render(<SuggestionsPage />);
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  it("shows empty state when no suggestions", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: null,
    });
    render(<SuggestionsPage />);
    expect(screen.getByText(/no suggestions/i)).toBeInTheDocument();
  });

  it("renders suggestion cards with accept/reject buttons", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [
        {
          id: "nugget-1",
          title: "Suggested Nugget",
          content: "Suggested content",
          tags: ["suggestion"],
          source_type: "llm_extracted",
          status: "suggested",
          created_at: "2024-06-15T12:00:00Z",
        },
      ],
      total: 1,
      isLoading: false,
      error: null,
    });
    render(<SuggestionsPage />);
    expect(screen.getByText("Suggested Nugget")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /accept/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reject/i }),
    ).toBeInTheDocument();
  });
});
