/**
 * Tests for EmptyState component — written FIRST (TDD Red phase).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No items found" description="Add your first item." />);
    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("renders the description", () => {
    render(<EmptyState title="No items found" description="Add your first item." />);
    expect(screen.getByText("Add your first item.")).toBeInTheDocument();
  });

  it("renders without an icon when none is provided", () => {
    const { container } = render(
      <EmptyState title="No items found" description="Add your first item." />
    );
    // Should render without crashing even when icon is omitted
    expect(container.firstChild).not.toBeNull();
  });

  it("renders icon content when icon prop is provided", () => {
    const TestIcon = () => <svg data-testid="test-icon" />;
    render(
      <EmptyState
        title="No items found"
        description="Add your first item."
        icon={<TestIcon />}
      />
    );
    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
  });
});
