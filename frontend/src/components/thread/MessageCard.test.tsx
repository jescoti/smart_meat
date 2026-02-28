/**
 * Tests for MessageCard component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MessageCard } from "./MessageCard";

describe("MessageCard", () => {
  const baseMessage = {
    id: "msg-1",
    sender_email: "alice@example.com",
    sender_name: "Alice Smith",
    subject: "Test Subject",
    body_text: "Hello, this is the message body.",
    body_html: null as string | null,
    gmail_date: "2024-01-12T09:00:00+00:00",
    depth: 0,
    is_ghost: false,
    parent_message_id: null as string | null,
  };

  it("renders sender name", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
  });

  it("renders sender email", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("renders date", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    // Should render some representation of the date
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it("renders plain text body when no HTML", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    expect(
      screen.getByText("Hello, this is the message body."),
    ).toBeInTheDocument();
  });

  it("renders HTML body when body_html is present", () => {
    const messageWithHtml = {
      ...baseMessage,
      body_html: "<p>Hello <strong>world</strong></p>",
    };
    render(
      <MessageCard message={messageWithHtml} threadSubject="Test Subject" />,
    );
    // HTML should be rendered - look for the strong tag content
    expect(screen.getByText("world")).toBeInTheDocument();
  });

  it("shows subject when different from thread subject", () => {
    const messageWithDiffSubject = {
      ...baseMessage,
      subject: "Different Subject",
    };
    render(
      <MessageCard
        message={messageWithDiffSubject}
        threadSubject="Test Subject"
      />,
    );
    expect(screen.getByText("Different Subject")).toBeInTheDocument();
  });

  it("does not show subject when same as thread subject", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    // The subject should not be displayed as a separate element when it matches
    const subjectElements = screen.queryAllByText("Test Subject");
    // There might be zero or it could show up in a heading, but it shouldn't
    // be rendered as a separate "subject" line
    expect(subjectElements.length).toBeLessThanOrEqual(0);
  });

  it("renders reply button", () => {
    render(<MessageCard message={baseMessage} threadSubject="Test Subject" />);
    expect(
      screen.getByRole("button", { name: /reply/i }),
    ).toBeInTheDocument();
  });

  it("uses sender_email when sender_name is null", () => {
    const messageNoName = {
      ...baseMessage,
      sender_name: null,
    };
    render(
      <MessageCard message={messageNoName} threadSubject="Test Subject" />,
    );
    // Should fall back to email for the name display
    const emails = screen.getAllByText("alice@example.com");
    expect(emails.length).toBeGreaterThanOrEqual(1);
  });

  it("handles null gmail_date", () => {
    const messageNoDate = {
      ...baseMessage,
      gmail_date: null,
    };
    render(
      <MessageCard message={messageNoDate} threadSubject="Test Subject" />,
    );
    // Should render without crashing
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
  });

  it("handles null body_text and null body_html", () => {
    const messageNoBody = {
      ...baseMessage,
      body_text: null,
      body_html: null,
    };
    render(
      <MessageCard
        message={{ ...messageNoBody, body_text: null as unknown as string }}
        threadSubject="Test Subject"
      />,
    );
    // Should not crash — renders without body content
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
  });
});
