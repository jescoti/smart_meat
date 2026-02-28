/**
 * Tests for the Consent page component.
 *
 * TDD RED phase -- these tests are written before the implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the consent module before importing the component
vi.mock("@/lib/consent", () => ({
  grantConsent: vi.fn(),
}));

import ConsentPage from "./page";
import { grantConsent } from "@/lib/consent";

const mockGrantConsent = vi.mocked(grantConsent);

beforeEach(() => {
  mockGrantConsent.mockClear();
  // Mock window.location.href
  Object.defineProperty(window, "location", {
    value: { href: "http://localhost:3000/consent" },
    writable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ConsentPage", () => {
  it("renders a heading", () => {
    render(<ConsentPage />);
    const heading = screen.getByRole("heading");
    expect(heading).toBeInTheDocument();
  });

  it("renders explanatory text about LLM processing", () => {
    render(<ConsentPage />);
    // Should mention that email content is processed by an AI/LLM
    expect(screen.getByText(/email/i)).toBeInTheDocument();
  });

  it("renders an agree button", () => {
    render(<ConsentPage />);
    const button = screen.getByRole("button", { name: /agree/i });
    expect(button).toBeInTheDocument();
  });

  it("renders a decline link or button", () => {
    render(<ConsentPage />);
    const decline = screen.getByRole("button", { name: /decline/i });
    expect(decline).toBeInTheDocument();
  });

  it("calls grantConsent when agree button is clicked", async () => {
    mockGrantConsent.mockResolvedValue(true);
    const user = userEvent.setup();

    render(<ConsentPage />);
    const button = screen.getByRole("button", { name: /agree/i });
    await user.click(button);

    expect(mockGrantConsent).toHaveBeenCalledTimes(1);
  });

  it("redirects to dashboard after successful consent", async () => {
    mockGrantConsent.mockResolvedValue(true);
    const user = userEvent.setup();

    render(<ConsentPage />);
    const button = screen.getByRole("button", { name: /agree/i });
    await user.click(button);

    expect(window.location.href).toBe("/dashboard");
  });

  it("redirects to dashboard when decline is clicked", async () => {
    const user = userEvent.setup();

    render(<ConsentPage />);
    const decline = screen.getByRole("button", { name: /decline/i });
    await user.click(decline);

    expect(window.location.href).toBe("/dashboard");
  });

  it("does not redirect if grantConsent fails", async () => {
    mockGrantConsent.mockResolvedValue(false);
    const user = userEvent.setup();

    render(<ConsentPage />);
    const button = screen.getByRole("button", { name: /agree/i });
    await user.click(button);

    // Should stay on current page since consent failed
    expect(window.location.href).toBe("http://localhost:3000/consent");
  });
});
