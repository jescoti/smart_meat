/**
 * Tests for ReplyComposer component.
 *
 * TDD RED phase -- tests written before implementation.
 * ReplyComposer provides a text area for composing a reply,
 * shows ReplyContext above it, has Send/Cancel buttons,
 * and includes a confirmation dialog before sending.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReplyComposer } from "./ReplyComposer";

describe("ReplyComposer", () => {
  const baseProps = {
    parentMessage: {
      id: "msg-1",
      sender_email: "alice@example.com",
      sender_name: "Alice Smith" as string | null,
      body_text: "Original message body text." as string | null,
      gmail_date: "2024-01-12T09:00:00+00:00" as string | null,
    },
    groupEmail: "test-group@googlegroups.com",
    onSend: vi.fn().mockResolvedValue(true),
    onCancel: vi.fn(),
    isLoading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the reply context with parent message info", () => {
    render(<ReplyComposer {...baseProps} />);
    expect(screen.getByText(/Alice Smith/)).toBeInTheDocument();
  });

  it("renders a text area for composing", () => {
    render(<ReplyComposer {...baseProps} />);
    expect(
      screen.getByPlaceholderText(/write your reply/i),
    ).toBeInTheDocument();
  });

  it("renders Send and Cancel buttons", () => {
    render(<ReplyComposer {...baseProps} />);
    expect(
      screen.getByRole("button", { name: /send/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel/i }),
    ).toBeInTheDocument();
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const user = userEvent.setup();
    render(<ReplyComposer {...baseProps} />);

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(baseProps.onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows confirmation dialog when Send is clicked", async () => {
    const user = userEvent.setup();
    render(<ReplyComposer {...baseProps} />);

    // Type something first
    await user.type(
      screen.getByPlaceholderText(/write your reply/i),
      "My reply text",
    );

    await user.click(screen.getByRole("button", { name: /send/i }));

    // Confirmation dialog should appear
    expect(
      screen.getByText(/send reply to test-group@googlegroups.com/i),
    ).toBeInTheDocument();
    // "Alice Smith" appears in both the ReplyContext and confirmation
    const aliceElements = screen.getAllByText(/Alice Smith/);
    expect(aliceElements.length).toBeGreaterThanOrEqual(2);
  });

  it("calls onSend with body text after confirmation", async () => {
    const user = userEvent.setup();
    render(<ReplyComposer {...baseProps} />);

    await user.type(
      screen.getByPlaceholderText(/write your reply/i),
      "My reply text",
    );

    // Click Send
    await user.click(screen.getByRole("button", { name: /send/i }));

    // Confirm
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(baseProps.onSend).toHaveBeenCalledWith("My reply text");
  });

  it("does not call onSend if confirmation is cancelled", async () => {
    const user = userEvent.setup();
    render(<ReplyComposer {...baseProps} />);

    await user.type(
      screen.getByPlaceholderText(/write your reply/i),
      "My reply text",
    );

    // Click Send
    await user.click(screen.getByRole("button", { name: /send/i }));

    // Cancel confirmation
    await user.click(
      screen.getByRole("button", { name: /go back/i }),
    );

    expect(baseProps.onSend).not.toHaveBeenCalled();
    // Confirmation dialog should be dismissed
    expect(
      screen.queryByText(/send reply to test-group@googlegroups.com/i),
    ).not.toBeInTheDocument();
  });

  it("disables Send button when text area is empty", () => {
    render(<ReplyComposer {...baseProps} />);

    const sendButton = screen.getByRole("button", { name: /send/i });
    expect(sendButton).toBeDisabled();
  });

  it("disables buttons when isLoading is true", () => {
    render(<ReplyComposer {...baseProps} isLoading={true} />);

    const sendButton = screen.getByRole("button", { name: /send/i });
    expect(sendButton).toBeDisabled();
  });

  it("shows loading state text when isLoading", () => {
    render(<ReplyComposer {...baseProps} isLoading={true} />);

    expect(screen.getByText(/sending/i)).toBeInTheDocument();
  });

  it("shows error message when provided", () => {
    render(<ReplyComposer {...baseProps} error="Failed to send reply" />);

    expect(screen.getByText(/failed to send reply/i)).toBeInTheDocument();
  });

  it("handles null sender_name in parent message", () => {
    render(
      <ReplyComposer
        {...baseProps}
        parentMessage={{ ...baseProps.parentMessage, sender_name: null }}
      />,
    );
    expect(screen.getByText(/alice@example.com/)).toBeInTheDocument();
  });

  it("handles null body_text in parent message", () => {
    render(
      <ReplyComposer
        {...baseProps}
        parentMessage={{ ...baseProps.parentMessage, body_text: null }}
      />,
    );
    // Should render without crashing
    expect(screen.getByPlaceholderText(/write your reply/i)).toBeInTheDocument();
  });

  it("handles null gmail_date in parent message", () => {
    render(
      <ReplyComposer
        {...baseProps}
        parentMessage={{ ...baseProps.parentMessage, gmail_date: null }}
      />,
    );
    // Should render without crashing
    expect(screen.getByText(/Alice Smith/)).toBeInTheDocument();
  });
});
