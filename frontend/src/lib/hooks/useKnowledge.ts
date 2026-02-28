/**
 * Hooks for knowledge base operations — nugget listing, detail, and mutations.
 *
 * Provides useNuggets, useNuggetDetail, useCreateNugget,
 * useAcceptNugget, and useRejectNugget hooks.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/** Shape of a nugget object returned from the API. */
export interface NuggetData {
  id: string;
  title: string;
  content: string;
  tags: string[];
  source_type: string;
  status: string;
  created_at: string | null;
}

/** Response shape from the nuggets list endpoint. */
interface NuggetsListResponse {
  nuggets: NuggetData[];
  total: number;
  page: number;
  per_page: number;
}

/**
 * Fetch and manage a paginated list of nuggets for a group.
 */
export function useNuggets(
  groupId: string,
  status: string | null,
  page: number,
): {
  nuggets: NuggetData[];
  total: number;
  isLoading: boolean;
  error: string | null;
} {
  const [nuggets, setNuggets] = useState<NuggetData[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNuggets = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      let url = `/api/knowledge/nuggets?group_id=${groupId}&page=${page}&per_page=20`;
      if (status) {
        url = `/api/knowledge/nuggets?group_id=${groupId}&status=${status}&page=${page}&per_page=20`;
      }
      const response = await apiFetch(url);
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Failed to load nuggets");
        return;
      }
      const data: NuggetsListResponse = await response.json();
      setNuggets(data.nuggets);
      setTotal(data.total);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, [groupId, status, page]);

  useEffect(() => {
    fetchNuggets();
  }, [fetchNuggets]);

  return { nuggets, total, isLoading, error };
}

/**
 * Fetch a single nugget by ID.
 */
export function useNuggetDetail(
  nuggetId: string | null,
): {
  nugget: NuggetData | null;
  isLoading: boolean;
  error: string | null;
} {
  const [nugget, setNugget] = useState<NuggetData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/knowledge/nuggets/${nuggetId}`);
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Failed to load nugget");
        return;
      }
      const data: NuggetData = await response.json();
      setNugget(data);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, [nuggetId]);

  useEffect(() => {
    if (nuggetId) {
      fetchDetail();
    }
  }, [nuggetId, fetchDetail]);

  return { nugget, isLoading, error };
}

/** Input shape for creating a manual nugget. */
interface CreateNuggetInput {
  group_id: string;
  title: string;
  content: string;
  tags: string[];
  source_message_id?: string;
}

/**
 * Mutation hook for creating a manual nugget.
 */
export function useCreateNugget(): {
  createNugget: (input: CreateNuggetInput) => Promise<void>;
  isLoading: boolean;
  error: string | null;
} {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createNugget = useCallback(async (input: CreateNuggetInput) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch("/api/knowledge/nuggets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Failed to create nugget");
        return;
      }
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { createNugget, isLoading, error };
}

/**
 * Mutation hook for accepting a suggested nugget.
 */
export function useAcceptNugget(): {
  acceptNugget: (nuggetId: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
} {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const acceptNugget = useCallback(async (nuggetId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch(
        `/api/knowledge/nuggets/${nuggetId}/accept`,
        { method: "POST" },
      );
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Failed to accept nugget");
        return;
      }
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { acceptNugget, isLoading, error };
}

/**
 * Mutation hook for rejecting a suggested nugget.
 */
export function useRejectNugget(): {
  rejectNugget: (nuggetId: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
} {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rejectNugget = useCallback(async (nuggetId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch(
        `/api/knowledge/nuggets/${nuggetId}/reject`,
        { method: "POST" },
      );
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Failed to reject nugget");
        return;
      }
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { rejectNugget, isLoading, error };
}
