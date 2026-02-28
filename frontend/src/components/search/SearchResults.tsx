/**
 * SearchResults -- renders a list of search result items.
 *
 * Each item shows the subject, sender, date, and snippet.
 * When sender_name is null, falls back to sender_email.
 */

"use client";

import type { SearchHit } from "@/lib/hooks/useSearch";

interface SearchResultsProps {
  results: SearchHit[];
}

function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function SearchResults({ results }: SearchResultsProps) {
  if (results.length === 0) {
    return null;
  }

  return (
    <ul className="divide-y divide-gray-200">
      {results.map((hit) => (
        <li key={hit.message_id} className="py-4">
          <div className="flex items-start justify-between">
            <h4 className="text-sm font-medium text-gray-900">
              {hit.subject}
            </h4>
            <span className="ml-2 text-xs text-gray-500 whitespace-nowrap">
              {formatDate(hit.gmail_date)}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-600">
            {hit.sender_name ?? hit.sender_email}
          </p>
          <p className="mt-1 text-sm text-gray-500">{hit.snippet}</p>
        </li>
      ))}
    </ul>
  );
}
