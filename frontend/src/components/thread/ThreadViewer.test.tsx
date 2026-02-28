/**
 * Tests for ThreadViewer component.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThreadViewer } from "./ThreadViewer";

const rootMessage = {
  id: "msg-1",
  sender_email: "alice@example.com",
  sender_name: "Alice",
  subject: "Thread Subject",
  body_text: "Root message body",
  body_html: null as string | null,
  gmail_date: "2024-01-12T09:00:00+00:00",
  depth: 0,
  is_ghost: false,
  parent_message_id: null as string | null,
};

const childMessage = {
  id: "msg-2",
  sender_email: "bob@example.com",
  sender_name: "Bob",
  subject: "Re: Thread Subject",
  body_text: "Reply message body",
  body_html: null as string | null,
  gmail_date: "2024-01-12T10:00:00+00:00",
  depth: 1,
  is_ghost: false,
  parent_message_id: "msg-1",
};

const ghostMessage = {
  id: "msg-3",
  sender_email: "",
  sender_name: null as string | null,
  subject: "",
  body_text: null as string | null,
  body_html: null as string | null,
  gmail_date: "2024-01-12T08:00:00+00:00",
  depth: 0,
  is_ghost: true,
  parent_message_id: null as string | null,
};

const deepChild = {
  id: "msg-4",
  sender_email: "charlie@example.com",
  sender_name: "Charlie",
  subject: "Re: Re: Thread Subject",
  body_text: "Deep reply",
  body_html: null as string | null,
  gmail_date: "2024-01-12T11:00:00+00:00",
  depth: 2,
  is_ghost: false,
  parent_message_id: "msg-2",
};

describe("ThreadViewer", () => {
  it("renders all messages", () => {
    render(
      <ThreadViewer
        messages={[rootMessage, childMessage]}
        threadSubject="Thread Subject"
      />,
    );
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders ghost messages with MissingMessageGhost", () => {
    render(
      <ThreadViewer
        messages={[ghostMessage, childMessage]}
        threadSubject="Thread Subject"
      />,
    );
    expect(
      screen.getByText(/message not available|not found in the archive/i),
    ).toBeInTheDocument();
  });

  it("indents messages based on depth", () => {
    const { container } = render(
      <ThreadViewer
        messages={[rootMessage, childMessage, deepChild]}
        threadSubject="Thread Subject"
      />,
    );
    // Messages at depth > 0 should have left margin/padding for indentation
    const messageContainers = container.querySelectorAll("[data-depth]");
    expect(messageContainers.length).toBe(3);
    expect(messageContainers[0].getAttribute("data-depth")).toBe("0");
    expect(messageContainers[1].getAttribute("data-depth")).toBe("1");
    expect(messageContainers[2].getAttribute("data-depth")).toBe("2");
  });

  it("toggles collapse/expand for thread branches", async () => {
    const user = userEvent.setup();
    render(
      <ThreadViewer
        messages={[rootMessage, childMessage]}
        threadSubject="Thread Subject"
      />,
    );

    // Both messages should be visible initially
    expect(screen.getByText("Root message body")).toBeInTheDocument();
    expect(screen.getByText("Reply message body")).toBeInTheDocument();

    // Find and click the collapse toggle on the root message
    const collapseButton = screen.getAllByRole("button", {
      name: /collapse|expand/i,
    })[0];
    await user.click(collapseButton);

    // Child message should be hidden
    expect(screen.queryByText("Reply message body")).not.toBeInTheDocument();

    // Click again to expand
    await user.click(collapseButton);

    // Child message should be visible again
    expect(screen.getByText("Reply message body")).toBeInTheDocument();
  });

  it("handles empty messages array", () => {
    const { container } = render(
      <ThreadViewer messages={[]} threadSubject="Thread Subject" />,
    );
    // Should render without crashing
    expect(container).toBeTruthy();
  });

  it("only shows collapse button for messages with children", () => {
    render(
      <ThreadViewer
        messages={[rootMessage, childMessage]}
        threadSubject="Thread Subject"
      />,
    );

    // Root message has a child, so it should have a collapse button
    // Child message has no children, so it should not have one
    const collapseButtons = screen.getAllByRole("button", {
      name: /collapse|expand/i,
    });
    // Only the root should have a collapse/expand button
    expect(collapseButtons).toHaveLength(1);
  });
});
