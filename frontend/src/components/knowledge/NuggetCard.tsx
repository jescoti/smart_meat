/**
 * NuggetCard -- displays a knowledge nugget with title, content preview,
 * tags, source type badge, and date.
 */

import type { NuggetData } from "@/lib/hooks/useKnowledge";

interface NuggetCardProps {
  nugget: NuggetData;
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

/**
 * Get a display label for the source type.
 */
function sourceTypeLabel(sourceType: string): string {
  if (sourceType === "llm_extracted") return "Extracted";
  return "Manual";
}

export function NuggetCard({ nugget }: NuggetCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-start justify-between">
        <h3 className="font-semibold text-gray-900">{nugget.title}</h3>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
            {sourceTypeLabel(nugget.source_type)}
          </span>
          <time className="text-sm text-gray-400">
            {formatDate(nugget.created_at)}
          </time>
        </div>
      </div>

      <p className="mb-2 text-sm text-gray-700">{nugget.content}</p>

      {nugget.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
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
    </div>
  );
}
