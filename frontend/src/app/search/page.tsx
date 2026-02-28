/**
 * Search page -- full-text search across messages.
 *
 * Provides a search bar, filter controls, result list,
 * pagination, loading state, and empty state.
 */

"use client";

import { useState } from "react";
import { useSearch } from "@/lib/hooks/useSearch";
import { SearchBar } from "@/components/search/SearchBar";
import { SearchResults } from "@/components/search/SearchResults";
import {
  SearchFilters,
  type SearchFilterValues,
} from "@/components/search/SearchFilters";
import { EmptyState } from "@/components/common/EmptyState";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<SearchFilterValues>({
    groupId: "",
    sender: "",
    dateFrom: "",
    dateTo: "",
  });

  const { results, total, perPage, isLoading, error } = useSearch(
    submittedQuery,
    {
      groupId: filters.groupId || undefined,
      sender: filters.sender || undefined,
      dateFrom: filters.dateFrom || undefined,
      dateTo: filters.dateTo || undefined,
    },
    page,
  );

  const totalPages = Math.ceil(total / perPage);
  const hasSearched = submittedQuery.trim() !== "";

  function handleSubmit() {
    setSubmittedQuery(query);
    setPage(1);
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Search</h1>

      <div className="mb-4">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSubmit={handleSubmit}
        />
      </div>

      <div className="mb-6">
        <SearchFilters filters={filters} onChange={setFilters} />
      </div>

      {isLoading && (
        <p className="text-sm text-gray-500">Searching...</p>
      )}

      {error != null && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {!isLoading && error == null && hasSearched && results.length === 0 && (
        <EmptyState
          title="No results found"
          description="Try adjusting your search terms or filters."
        />
      )}

      {!isLoading && error == null && results.length > 0 && (
        <>
          <SearchResults results={results} />

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-md border border-gray-300 px-3 py-1 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-md border border-gray-300 px-3 py-1 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
