/**
 * Suggestions page -- pending nuggets with accept/reject UI.
 *
 * Lists all suggested (pending) nuggets from LLM extraction.
 * Users can accept or reject each suggestion.
 */

"use client";

import {
  useNuggets,
  useAcceptNugget,
  useRejectNugget,
} from "@/lib/hooks/useKnowledge";
import { NuggetSuggestionCard } from "@/components/knowledge/NuggetSuggestionCard";

export default function SuggestionsPage() {
  const { nuggets, isLoading, error } = useNuggets(
    "default-group",
    "suggested",
    1,
  );
  const { acceptNugget } = useAcceptNugget();
  const { rejectNugget } = useRejectNugget();

  async function handleAccept(nuggetId: string) {
    await acceptNugget(nuggetId);
  }

  async function handleReject(nuggetId: string) {
    await rejectNugget(nuggetId);
  }

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">Suggestions</h1>

      {isLoading && <p className="text-gray-500">Loading suggestions...</p>}

      {error && <p className="text-red-600">{error}</p>}

      {!isLoading && !error && nuggets.length === 0 && (
        <p className="text-gray-500">
          No suggestions yet. Extract knowledge from threads to see suggestions
          here.
        </p>
      )}

      {nuggets.length > 0 && (
        <div className="space-y-4">
          {nuggets.map((nugget) => (
            <NuggetSuggestionCard
              key={nugget.id}
              nugget={nugget}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </main>
  );
}
