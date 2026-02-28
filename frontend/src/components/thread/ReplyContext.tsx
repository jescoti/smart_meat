/**
 * ReplyContext -- shows a quoted parent message for reply context.
 *
 * Displays the first 3 lines of body_text, sender name, and date
 * in a visual quote block style (left border, muted colors).
 */

interface ReplyContextProps {
  senderName: string | null;
  senderEmail: string;
  bodyText: string | null;
  date: string | null;
}

/**
 * Format an ISO date string for display.
 */
function formatDate(isoDate: string): string {
  const d = new Date(isoDate);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Get the first N lines of text.
 */
function getFirstLines(text: string | null, maxLines: number): string {
  if (!text) return "";
  const lines = text.split("\n");
  return lines.slice(0, maxLines).join("\n");
}

export function ReplyContext({
  senderName,
  senderEmail,
  bodyText,
  date,
}: ReplyContextProps) {
  const displayName = senderName ?? senderEmail;
  const quotedText = getFirstLines(bodyText, 3);

  return (
    <div
      data-testid="reply-context"
      className="border-l-4 border-gray-300 bg-gray-50 pl-3 py-2 text-sm text-gray-600"
    >
      <div className="mb-1">
        <span className="font-medium text-gray-700">{displayName}</span>
        {date && (
          <span className="ml-2 text-gray-400">{formatDate(date)}</span>
        )}
      </div>
      {quotedText && (
        <p className="whitespace-pre-wrap text-gray-500">{quotedText}</p>
      )}
    </div>
  );
}
