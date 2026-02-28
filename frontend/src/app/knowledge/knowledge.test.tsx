/**
 * Tests for the Knowledge base browser page.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks/useKnowledge", () => ({
  useNuggets: vi.fn(),
}));

import KnowledgePage from "./page";
import { useNuggets } from "@/lib/hooks/useKnowledge";

const mockUseNuggets = vi.mocked(useNuggets);

beforeEach(() => {
  mockUseNuggets.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("KnowledgePage", () => {
  it("renders a heading", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: null,
    });
    render(<KnowledgePage />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: true,
      error: null,
    });
    render(<KnowledgePage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: "Failed to load",
    });
    render(<KnowledgePage />);
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  it("shows empty state when no nuggets", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [],
      total: 0,
      isLoading: false,
      error: null,
    });
    render(<KnowledgePage />);
    expect(screen.getByText(/no nuggets/i)).toBeInTheDocument();
  });

  it("renders nugget cards", () => {
    mockUseNuggets.mockReturnValue({
      nuggets: [
        {
          id: "nugget-1",
          title: "Test Nugget",
          content: "Test content",
          tags: ["test"],
          source_type: "manual",
          status: "accepted",
          created_at: "2024-06-15T12:00:00Z",
        },
      ],
      total: 1,
      isLoading: false,
      error: null,
    });
    render(<KnowledgePage />);
    expect(screen.getByText("Test Nugget")).toBeInTheDocument();
  });
});
