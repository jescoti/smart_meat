/**
 * Tests for the Login page component.
 *
 * TDD RED phase — these tests are written before the implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the auth module before importing the component
vi.mock("@/lib/auth", () => ({
  getLoginUrl: vi.fn(),
}));

import LoginPage from "./page";
import { getLoginUrl } from "@/lib/auth";

const mockGetLoginUrl = vi.mocked(getLoginUrl);

beforeEach(() => {
  mockGetLoginUrl.mockClear();
  // Mock window.location.href
  Object.defineProperty(window, "location", {
    value: { href: "http://localhost:3000/login" },
    writable: true,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LoginPage", () => {
  it("renders a sign-in button", () => {
    render(<LoginPage />);
    const button = screen.getByRole("button", { name: /sign in with google/i });
    expect(button).toBeInTheDocument();
  });

  it("calls getLoginUrl when button is clicked", async () => {
    mockGetLoginUrl.mockResolvedValue("https://accounts.google.com/auth");
    const user = userEvent.setup();

    render(<LoginPage />);
    const button = screen.getByRole("button", { name: /sign in with google/i });
    await user.click(button);

    expect(mockGetLoginUrl).toHaveBeenCalledTimes(1);
  });

  it("redirects to the returned URL on button click", async () => {
    const authUrl = "https://accounts.google.com/o/oauth2/v2/auth?test=1";
    mockGetLoginUrl.mockResolvedValue(authUrl);
    const user = userEvent.setup();

    render(<LoginPage />);
    const button = screen.getByRole("button", { name: /sign in with google/i });
    await user.click(button);

    expect(window.location.href).toBe(authUrl);
  });

  it("renders the page heading", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });
});
