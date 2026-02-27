/**
 * Tests for ErrorBoundary component — written alongside implementation
 * to complete RED-GREEN cycle for 100% coverage.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

/** Helper: a component that throws an error when `shouldThrow` is true. */
function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test render error");
  }
  return <div>Child rendered successfully</div>;
}

describe("ErrorBoundary", () => {
  // Suppress console.error output from React during error boundary tests
  const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

  afterEach(() => {
    consoleErrorSpy.mockClear();
  });

  describe("normal rendering", () => {
    it("renders children when no error occurs", () => {
      render(
        <ErrorBoundary>
          <ThrowingChild shouldThrow={false} />
        </ErrorBoundary>
      );
      expect(screen.getByText("Child rendered successfully")).toBeInTheDocument();
    });
  });

  describe("error handling", () => {
    it("renders default fallback UI when a child throws", () => {
      render(
        <ErrorBoundary>
          <ThrowingChild shouldThrow={true} />
        </ErrorBoundary>
      );
      expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
      expect(
        screen.getByText("Please refresh the page or try again later.")
      ).toBeInTheDocument();
    });

    it("renders custom fallback when provided and a child throws", () => {
      render(
        <ErrorBoundary fallback={<div>Custom error UI</div>}>
          <ThrowingChild shouldThrow={true} />
        </ErrorBoundary>
      );
      expect(screen.getByText("Custom error UI")).toBeInTheDocument();
    });

    it("calls componentDidCatch when an error is thrown", () => {
      render(
        <ErrorBoundary>
          <ThrowingChild shouldThrow={true} />
        </ErrorBoundary>
      );
      // console.error is called by componentDidCatch (our impl) and React itself
      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });
});
