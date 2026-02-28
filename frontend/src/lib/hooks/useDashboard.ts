/**
 * Hook for fetching the dashboard summary from the API.
 *
 * Provides useDashboard hook that returns aggregated counts
 * and recent items for the user's groups, threads, and nuggets.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/** Shape of a recent thread in the dashboard summary. */
export interface DashboardThread {
  subject: string;
  group_name: string;
  message_count: number;
  last_activity: string | null;
}

/** Shape of a recent nugget in the dashboard summary. */
export interface DashboardNugget {
  content_preview: string;
  source_thread_subject: string | null;
}

/** Response shape from the dashboard summary endpoint. */
export interface DashboardSummary {
  groups_count: number;
  threads_count: number;
  nuggets_count: number;
  recent_threads: DashboardThread[];
  recent_nuggets: DashboardNugget[];
}

/**
 * Fetch the dashboard summary for the authenticated user.
 *
 * Fetches on mount and returns data, loading, and error states.
 */
export function useDashboard(): {
  data: DashboardSummary | null;
  isLoading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiFetch("/api/dashboard/summary");
      if (!response.ok) {
        const errorData = await response.json();
        setError(errorData.message || "Failed to load dashboard");
        return;
      }

      const summaryData: DashboardSummary = await response.json();
      setData(summaryData);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  return { data, isLoading, error };
}
