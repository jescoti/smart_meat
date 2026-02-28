/**
 * Tests for the SyncError component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import SyncError from "./SyncError";

describe("SyncError", () => {
  it("renders the error message", () => {
    render(<SyncError message="Rate limited" onRetry={() => {}} />);
    expect(screen.getByText("Rate limited")).toBeInTheDocument();
  });

  it("renders a retry button", () => {
    render(<SyncError message="Rate limited" onRetry={() => {}} />);
    expect(
      screen.getByRole("button", { name: /retry/i }),
    ).toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(<SyncError message="Rate limited" onRetry={onRetry} />);

    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders an error icon or heading", () => {
    render(<SyncError message="Something went wrong" onRetry={() => {}} />);
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
