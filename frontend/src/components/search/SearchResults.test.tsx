/**
 * Tests for the SearchResults component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { SearchResults } from "./SearchResults";
import type { SearchHit } from "@/lib/hooks/useSearch";

const makeHit = (overrides: Partial<SearchHit> = {}): SearchHit => ({
  message_id: "msg-1",
  subject: "Meeting Notes",
  sender_name: "Alice",
  sender_email: "alice@example.com",
  gmail_date: "2024-01-12T09:00:00+00:00",
  snippet: "Notes from our weekly meeting...",
  group_id: "group-1",
  thread_id: "thread-1",
  rank: 0.75,
  ...overrides,
});

describe("SearchResults", () => {
  it("renders a list of results", () => {
    render(<SearchResults results={[makeHit(), makeHit({ message_id: "msg-2", subject: "Other" })]} />);

    expect(screen.getByText("Meeting Notes")).toBeInTheDocument();
    expect(screen.getByText("Other")).toBeInTheDocument();
  });

  it("renders the subject", () => {
    render(<SearchResults results={[makeHit({ subject: "Project Update" })]} />);

    expect(screen.getByText("Project Update")).toBeInTheDocument();
  });

  it("renders the sender name", () => {
    render(<SearchResults results={[makeHit({ sender_name: "Bob" })]} />);

    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it("renders sender email when name is null", () => {
    render(
      <SearchResults results={[makeHit({ sender_name: null, sender_email: "bob@example.com" })]} />,
    );

    expect(screen.getByText(/bob@example.com/)).toBeInTheDocument();
  });

  it("renders the date", () => {
    render(
      <SearchResults
        results={[makeHit({ gmail_date: "2024-03-15T14:30:00+00:00" })]}
      />,
    );

    // Should display a formatted date string
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it("renders the snippet", () => {
    render(
      <SearchResults
        results={[makeHit({ snippet: "Important discussion about..." })]}
      />,
    );

    expect(
      screen.getByText("Important discussion about..."),
    ).toBeInTheDocument();
  });

  it("renders empty when no results", () => {
    const { container } = render(<SearchResults results={[]} />);

    // Should not render any list items
    expect(container.querySelectorAll("li")).toHaveLength(0);
  });
});
