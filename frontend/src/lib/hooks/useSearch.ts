/**
 * Hook for searching messages via the search API.
 *
 * Provides useSearch hook for fetching paginated search results
 * with optional filters (group, sender, date range).
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/** Shape of a search result item returned from the API. */
export interface SearchHit {
  message_id: string;
  subject: string;
  sender_name: string | null;
  sender_email: string;
  gmail_date: string;
  snippet: string;
  group_id: string;
  thread_id: string | null;
  rank: number;
}

/** Optional filter values for search. */
export interface SearchFilters {
  groupId?: string;
  sender?: string;
  dateFrom?: string;
  dateTo?: string;
}

/** Response shape from the search endpoint. */
interface SearchResponse {
  results: SearchHit[];
  total: number;
  page: number;
  per_page: number;
}

/**
 * Fetch and manage search results.
 *
 * Only fetches when the query is non-empty (after trimming).
 * Clears results when the query becomes empty.
 */
export function useSearch(
  query: string,
  filters: SearchFilters,
  page: number = 1,
  perPage: number = 20,
): {
  results: SearchHit[];
  total: number;
  page: number;
  perPage: number;
  isLoading: boolean;
  error: string | null;
} {
  const [results, setResults] = useState<SearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(page);
  const [currentPerPage, setCurrentPerPage] = useState(perPage);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmedQuery = query.trim();

  const fetchResults = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("q", trimmedQuery);
      params.set("page", String(page));
      params.set("per_page", String(perPage));

      if (filters.groupId) {
        params.set("group_id", filters.groupId);
      }
      if (filters.sender) {
        params.set("sender", filters.sender);
      }
      if (filters.dateFrom) {
        params.set("date_from", filters.dateFrom);
      }
      if (filters.dateTo) {
        params.set("date_to", filters.dateTo);
      }

      const response = await apiFetch(`/api/search?${params.toString()}`);
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Search failed");
        return;
      }

      const data: SearchResponse = await response.json();
      setResults(data.results);
      setTotal(data.total);
      setCurrentPage(data.page);
      setCurrentPerPage(data.per_page);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, [trimmedQuery, filters.groupId, filters.sender, filters.dateFrom, filters.dateTo, page, perPage]);

  useEffect(() => {
    if (trimmedQuery === "") {
      setResults([]);
      setTotal(0);
      setIsLoading(false);
      setError(null);
      return;
    }
    fetchResults();
  }, [fetchResults, trimmedQuery]);

  return {
    results,
    total,
    page: currentPage,
    perPage: currentPerPage,
    isLoading,
    error,
  };
}
