/**
 * NuggetSuggestionCard -- like NuggetCard but with Accept/Reject buttons
 * for pending suggestions.
 */

import type { NuggetData } from "@/lib/hooks/useKnowledge";

interface NuggetSuggestionCardProps {
  nugget: NuggetData;
  onAccept: (nuggetId: string) => void;
  onReject: (nuggetId: string) => void;
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
  });
}

export function NuggetSuggestionCard({
  nugget,
  onAccept,
  onReject,
}: NuggetSuggestionCardProps) {
  return (
    <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 shadow-sm">
      <div className="mb-2 flex items-start justify-between">
        <h3 className="font-semibold text-gray-900">{nugget.title}</h3>
        <time className="text-sm text-gray-400">
          {formatDate(nugget.created_at)}
        </time>
      </div>

      <p className="mb-2 text-sm text-gray-700">{nugget.content}</p>

      {nugget.tags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          {nugget.tags.map((tag) => (
            <span
              key={tag}
              className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          className="rounded bg-red-100 px-3 py-1 text-sm text-red-700 hover:bg-red-200"
          onClick={() => onReject(nugget.id)}
        >
          Reject
        </button>
        <button
          type="button"
          className="rounded bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700"
          onClick={() => onAccept(nugget.id)}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
