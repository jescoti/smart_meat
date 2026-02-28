/**
 * Tests for NuggetCard component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NuggetCard } from "./NuggetCard";

describe("NuggetCard", () => {
  const baseNugget = {
    id: "nugget-1",
    title: "Important Decision",
    content: "The team decided to use PostgreSQL for the database.",
    tags: ["database", "decision"],
    source_type: "manual" as const,
    status: "accepted" as const,
    created_at: "2024-06-15T12:00:00Z",
  };

  it("renders nugget title", () => {
    render(<NuggetCard nugget={baseNugget} />);
    expect(screen.getByText("Important Decision")).toBeInTheDocument();
  });

  it("renders nugget content", () => {
    render(<NuggetCard nugget={baseNugget} />);
    expect(
      screen.getByText(
        "The team decided to use PostgreSQL for the database.",
      ),
    ).toBeInTheDocument();
  });

  it("renders tags", () => {
    render(<NuggetCard nugget={baseNugget} />);
    expect(screen.getByText("database")).toBeInTheDocument();
    expect(screen.getByText("decision")).toBeInTheDocument();
  });

  it("renders source type badge", () => {
    render(<NuggetCard nugget={baseNugget} />);
    expect(screen.getByText(/manual/i)).toBeInTheDocument();
  });

  it("renders llm_extracted badge for LLM nuggets", () => {
    const llmNugget = { ...baseNugget, source_type: "llm_extracted" as const };
    render(<NuggetCard nugget={llmNugget} />);
    expect(screen.getByText(/extracted/i)).toBeInTheDocument();
  });

  it("renders date", () => {
    render(<NuggetCard nugget={baseNugget} />);
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it("handles empty tags", () => {
    const noTagsNugget = { ...baseNugget, tags: [] };
    render(<NuggetCard nugget={noTagsNugget} />);
    expect(screen.getByText("Important Decision")).toBeInTheDocument();
  });

  it("handles null created_at", () => {
    const noDateNugget = { ...baseNugget, created_at: null };
    render(<NuggetCard nugget={noDateNugget} />);
    expect(screen.getByText("Important Decision")).toBeInTheDocument();
  });
});
