/**
 * Tests for MissingMessageGhost component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MissingMessageGhost } from "./MissingMessageGhost";

describe("MissingMessageGhost", () => {
  it("renders a ghost placeholder", () => {
    render(<MissingMessageGhost />);
    expect(
      screen.getByText(/message not available|not found in the archive/i),
    ).toBeInTheDocument();
  });

  it("has dashed border styling", () => {
    const { container } = render(<MissingMessageGhost />);
    const ghostEl = container.firstChild as HTMLElement;
    expect(ghostEl.className).toContain("border-dashed");
  });

  it("is visually distinct with lighter colors", () => {
    const { container } = render(<MissingMessageGhost />);
    const ghostEl = container.firstChild as HTMLElement;
    // Should have lighter background or text color
    expect(ghostEl.className).toContain("text-gray");
  });
});
