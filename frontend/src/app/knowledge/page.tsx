/**
 * Knowledge base browser page.
 *
 * Lists accepted and manual nuggets. Allows filtering by group.
 */

"use client";

import { useNuggets } from "@/lib/hooks/useKnowledge";
import { NuggetCard } from "@/components/knowledge/NuggetCard";

export default function KnowledgePage() {
  // For now, use a placeholder group ID — in production this would come
  // from route params or a group selector.
  const { nuggets, total, isLoading, error } = useNuggets(
    "default-group",
    null,
    1,
  );

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">Knowledge Base</h1>

      {isLoading && <p className="text-gray-500">Loading nuggets...</p>}

      {error && <p className="text-red-600">{error}</p>}

      {!isLoading && !error && nuggets.length === 0 && (
        <p className="text-gray-500">
          No nuggets yet. Create a note or extract knowledge from threads.
        </p>
      )}

      {nuggets.length > 0 && (
        <div className="space-y-4">
          {nuggets.map((nugget) => (
            <NuggetCard key={nugget.id} nugget={nugget} />
          ))}
        </div>
      )}

      {total > 0 && (
        <p className="mt-4 text-sm text-gray-400">
          Showing {nuggets.length} of {total} nuggets
        </p>
      )}
    </main>
  );
}
