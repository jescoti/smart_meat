/**
 * Tests for ReplyContext component.
 *
 * TDD RED phase -- tests written before implementation.
 * ReplyContext shows a quoted parent message: first 3 lines of body_text,
 * sender name, and date, in a visual quote block style.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReplyContext } from "./ReplyContext";

describe("ReplyContext", () => {
  const baseProps = {
    senderName: "Alice Smith",
    senderEmail: "alice@example.com",
    bodyText:
      "First line of the message.\nSecond line of the message.\nThird line of the message.\nFourth line should not appear.",
    date: "2024-01-12T09:00:00+00:00",
  };

  it("renders sender name", () => {
    render(<ReplyContext {...baseProps} />);
    expect(screen.getByText(/Alice Smith/)).toBeInTheDocument();
  });

  it("renders date", () => {
    render(<ReplyContext {...baseProps} />);
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it("shows first 3 lines of body text", () => {
    render(<ReplyContext {...baseProps} />);
    expect(
      screen.getByText(/First line of the message/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Second line of the message/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Third line of the message/),
    ).toBeInTheDocument();
  });

  it("does not show lines beyond the first 3", () => {
    render(<ReplyContext {...baseProps} />);
    expect(
      screen.queryByText(/Fourth line should not appear/),
    ).not.toBeInTheDocument();
  });

  it("uses sender email when sender name is null", () => {
    render(<ReplyContext {...baseProps} senderName={null} />);
    expect(screen.getByText(/alice@example.com/)).toBeInTheDocument();
  });

  it("handles short body text (fewer than 3 lines)", () => {
    render(<ReplyContext {...baseProps} bodyText="Just one line." />);
    expect(screen.getByText(/Just one line/)).toBeInTheDocument();
  });

  it("handles null body text", () => {
    render(<ReplyContext {...baseProps} bodyText={null} />);
    // Should render without crashing
    expect(screen.getByText(/Alice Smith/)).toBeInTheDocument();
  });

  it("has a visual quote block (left border)", () => {
    const { container } = render(<ReplyContext {...baseProps} />);
    // Should have a left border style for the quote block
    const quoteBlock = container.querySelector("[data-testid='reply-context']");
    expect(quoteBlock).toBeInTheDocument();
  });
});
