/**
 * Tests for LoadingState component — written FIRST (TDD Red phase).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingState } from "./LoadingState";

describe("LoadingState", () => {
  it("renders without crashing", () => {
    const { container } = render(<LoadingState />);
    expect(container.firstChild).not.toBeNull();
  });

  it("has a loading indicator in the DOM", () => {
    render(<LoadingState />);
    // Must render some kind of loading visual — aria-label or role="status"
    const spinner = screen.getByRole("status");
    expect(spinner).toBeInTheDocument();
  });

  it("renders an accessible label for screen readers", () => {
    render(<LoadingState />);
    // Accessible loading text must be present
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });
});
