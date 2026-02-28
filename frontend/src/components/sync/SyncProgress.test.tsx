/**
 * Tests for the SyncProgress component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import SyncProgress from "./SyncProgress";

describe("SyncProgress", () => {
  it("renders a progress bar", () => {
    render(<SyncProgress current={5} total={10} />);
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toBeInTheDocument();
  });

  it("displays the percentage", () => {
    render(<SyncProgress current={5} total={10} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("displays 0% when total is 0", () => {
    render(<SyncProgress current={0} total={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("displays 100% when current equals total", () => {
    render(<SyncProgress current={10} total={10} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("displays status text when provided", () => {
    render(<SyncProgress current={5} total={10} statusText="Syncing messages..." />);
    expect(screen.getByText("Syncing messages...")).toBeInTheDocument();
  });

  it("sets correct aria-valuenow", () => {
    render(<SyncProgress current={3} total={10} />);
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuenow", "30");
  });

  it("sets correct aria-valuemin and aria-valuemax", () => {
    render(<SyncProgress current={3} total={10} />);
    const progressBar = screen.getByRole("progressbar");
    expect(progressBar).toHaveAttribute("aria-valuemin", "0");
    expect(progressBar).toHaveAttribute("aria-valuemax", "100");
  });

  it("handles null current gracefully", () => {
    render(<SyncProgress current={null} total={10} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("handles null total gracefully", () => {
    render(<SyncProgress current={5} total={null} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});
