/**
 * ReplyComposer -- compose and send a reply to a message.
 *
 * Features:
 * - Shows ReplyContext with parent message quote
 * - Text area for composing plain text reply
 * - Send and Cancel buttons
 * - Confirmation dialog before sending
 * - Loading and error state display
 */

"use client";

import { useState } from "react";
import { ReplyContext } from "./ReplyContext";

interface ParentMessageInfo {
  id: string;
  sender_email: string;
  sender_name: string | null;
  body_text: string | null;
  gmail_date: string | null;
}

interface ReplyComposerProps {
  parentMessage: ParentMessageInfo;
  groupEmail: string;
  onSend: (bodyText: string) => Promise<boolean>;
  onCancel: () => void;
  isLoading: boolean;
  error?: string | null;
}

export function ReplyComposer({
  parentMessage,
  groupEmail,
  onSend,
  onCancel,
  isLoading,
  error,
}: ReplyComposerProps) {
  const [bodyText, setBodyText] = useState("");
  const [showConfirmation, setShowConfirmation] = useState(false);

  const senderDisplay =
    parentMessage.sender_name ?? parentMessage.sender_email;

  function handleSendClick() {
    setShowConfirmation(true);
  }

  async function handleConfirm() {
    setShowConfirmation(false);
    await onSend(bodyText);
  }

  function handleGoBack() {
    setShowConfirmation(false);
  }

  const canSend = bodyText.trim().length > 0 && !isLoading;

  return (
    <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
      {/* Parent message context */}
      <ReplyContext
        senderName={parentMessage.sender_name}
        senderEmail={parentMessage.sender_email}
        bodyText={parentMessage.body_text}
        date={parentMessage.gmail_date}
      />

      {/* Confirmation dialog */}
      {showConfirmation && (
        <div className="my-3 rounded border border-yellow-300 bg-yellow-50 p-3 text-sm">
          <p className="mb-2">
            Send reply to {groupEmail} in response to {senderDisplay}
            &apos;s message?
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleConfirm}
              className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
            >
              Confirm
            </button>
            <button
              type="button"
              onClick={handleGoBack}
              className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-100"
            >
              Go back
            </button>
          </div>
        </div>
      )}

      {/* Text area */}
      <textarea
        className="mt-3 w-full rounded border border-gray-300 p-2 text-sm"
        rows={4}
        placeholder="Write your reply..."
        value={bodyText}
        onChange={(e) => setBodyText(e.target.value)}
        disabled={isLoading}
      />

      {/* Error message */}
      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}

      {/* Action buttons */}
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={handleSendClick}
          disabled={!canSend}
          className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Sending..." : "Send"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
