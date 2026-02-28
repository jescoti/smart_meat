/**
 * Tests for NuggetSuggestionCard component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NuggetSuggestionCard } from "./NuggetSuggestionCard";

describe("NuggetSuggestionCard", () => {
  const baseNugget = {
    id: "nugget-1",
    title: "Extracted Insight",
    content: "The project deadline was moved to next Friday.",
    tags: ["deadline", "planning"],
    source_type: "llm_extracted" as const,
    status: "suggested" as const,
    created_at: "2024-06-15T12:00:00Z",
  };

  it("renders nugget title", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText("Extracted Insight")).toBeInTheDocument();
  });

  it("renders nugget content", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(
      screen.getByText(
        "The project deadline was moved to next Friday.",
      ),
    ).toBeInTheDocument();
  });

  it("renders tags", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText("deadline")).toBeInTheDocument();
    expect(screen.getByText("planning")).toBeInTheDocument();
  });

  it("renders accept button", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /accept/i }),
    ).toBeInTheDocument();
  });

  it("renders reject button", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /reject/i }),
    ).toBeInTheDocument();
  });

  it("calls onAccept when accept button is clicked", async () => {
    const onAccept = vi.fn();
    const user = userEvent.setup();

    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={onAccept}
        onReject={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /accept/i }));
    expect(onAccept).toHaveBeenCalledWith("nugget-1");
  });

  it("calls onReject when reject button is clicked", async () => {
    const onReject = vi.fn();
    const user = userEvent.setup();

    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={onReject}
      />,
    );

    await user.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith("nugget-1");
  });

  it("renders date", () => {
    render(
      <NuggetSuggestionCard
        nugget={baseNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it("handles empty tags", () => {
    const noTagsNugget = { ...baseNugget, tags: [] };
    render(
      <NuggetSuggestionCard
        nugget={noTagsNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText("Extracted Insight")).toBeInTheDocument();
  });

  it("handles null created_at", () => {
    const noDateNugget = { ...baseNugget, created_at: null };
    render(
      <NuggetSuggestionCard
        nugget={noDateNugget}
        onAccept={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText("Extracted Insight")).toBeInTheDocument();
  });
});
