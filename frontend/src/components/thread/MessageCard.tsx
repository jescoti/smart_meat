/**
 * MessageCard -- renders a single message in a thread.
 *
 * Displays sender info, date, subject (if different from thread),
 * and message body (HTML or plain text). Includes a Reply button
 * that triggers the onReply callback when clicked.
 */

import type { ThreadMessageData } from "@/lib/hooks/useThreads";

interface MessageCardProps {
  message: ThreadMessageData;
  threadSubject: string;
  onReply?: () => void;
}

/**
 * Format an ISO date string for display.
 */
function formatDate(isoDate: string | null): string {
  if (!isoDate) return "";
  const date = new Date(isoDate);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MessageCard({
  message,
  threadSubject,
  onReply,
}: MessageCardProps) {
  const displayName = message.sender_name ?? message.sender_email;
  const showSubject =
    message.subject !== threadSubject && message.subject.length > 0;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {/* Header: sender info and date */}
      <div className="mb-2 flex items-start justify-between">
        <div>
          <span className="font-semibold text-gray-900">{displayName}</span>
          {message.sender_name && (
            <span className="ml-2 text-sm text-gray-500">
              {message.sender_email}
            </span>
          )}
        </div>
        <time className="text-sm text-gray-400">
          {formatDate(message.gmail_date)}
        </time>
      </div>

      {/* Subject line — only if different from thread subject */}
      {showSubject && (
        <p className="mb-2 text-sm font-medium text-gray-700">
          {message.subject}
        </p>
      )}

      {/* Message body */}
      <div className="prose prose-sm max-w-none text-gray-800">
        {message.body_html ? (
          <div dangerouslySetInnerHTML={{ __html: message.body_html }} />
        ) : (
          message.body_text && (
            <p className="whitespace-pre-wrap">{message.body_text}</p>
          )
        )}
      </div>

      {/* Actions */}
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          className="rounded px-3 py-1 text-sm text-blue-600 hover:bg-blue-50"
          onClick={onReply}
        >
          Reply
        </button>
      </div>
    </div>
  );
}
