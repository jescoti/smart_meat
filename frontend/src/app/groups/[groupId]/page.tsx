/**
 * Group Threads page -- lists threads for a group sorted by last activity.
 *
 * Features:
 * - Paginated thread list
 * - Each thread shows subject, message count, participant count, last activity
 * - Click navigates to thread detail
 * - Pagination controls (Previous/Next)
 * - Empty state when no threads
 */

"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useThreadList } from "@/lib/hooks/useThreads";

/**
 * Format an ISO date string for display as relative or absolute time.
 */
function formatLastActivity(isoDate: string | null): string {
  if (!isoDate) return "No activity";
  const date = new Date(isoDate);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function GroupThreadsPage() {
  const params = useParams();
  const router = useRouter();
  const groupId = params.groupId as string;
  const [page, setPage] = useState(1);
  const perPage = 20;

  const { threads, total, isLoading, error } = useThreadList(
    groupId,
    page,
    perPage,
  );

  const totalPages = Math.ceil(total / perPage);
  const hasNextPage = page < totalPages;
  const hasPrevPage = page > 1;

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">Threads</h1>

      {isLoading && <p className="text-gray-500">Loading threads...</p>}

      {error && <p className="text-red-600">{error}</p>}

      {!isLoading && !error && threads.length === 0 && (
        <p className="text-gray-500">
          No threads yet. Messages will appear here after syncing.
        </p>
      )}

      {threads.length > 0 && (
        <ul className="space-y-3">
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                onClick={() =>
                  router.push(`/groups/${groupId}/threads/${thread.id}`)
                }
                className="w-full rounded-lg border border-gray-200 p-4 text-left transition-colors hover:bg-gray-50"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-900">
                      {thread.subject}
                    </p>
                    <div className="mt-1 flex gap-4 text-sm text-gray-500">
                      <span>{thread.message_count} messages</span>
                      <span>{thread.participant_count} participants</span>
                    </div>
                  </div>
                  <span className="ml-4 flex-shrink-0 text-sm text-gray-400">
                    {formatLastActivity(thread.last_message_at)}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Pagination */}
      {total > 0 && (
        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((p) => p - 1)}
            disabled={!hasPrevPage}
            className="rounded bg-gray-100 px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasNextPage}
            className="rounded bg-gray-100 px-4 py-2 text-sm text-gray-700 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </main>
  );
}
