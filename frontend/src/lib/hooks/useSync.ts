/**
 * Hooks for group management and sync operations.
 *
 * Provides useGroups, useSyncStatus, useTriggerSync, and useAddGroup hooks
 * for managing Google Group sync in the frontend.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";

/** Shape of a group object returned from the API. */
export interface GroupData {
  id: string;
  gmail_group_email: string;
  display_name: string;
  sync_status: string;
  sync_error_message: string | null;
  sync_progress_current: number | null;
  sync_progress_total: number | null;
}

/** Shape of a sync status response. */
interface SyncStatusResponse {
  status: string;
  progress_current: number | null;
  progress_total: number | null;
  error_message: string | null;
}

/** Polling interval for sync status (milliseconds). */
const POLL_INTERVAL_MS = 5000;

/**
 * Fetch and manage the list of groups for the authenticated user.
 */
export function useGroups(): {
  groups: GroupData[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [groups, setGroups] = useState<GroupData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGroups = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch("/api/groups");
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Failed to load groups");
        return;
      }
      const data = await response.json();
      setGroups(data);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  return { groups, loading, error, refresh: fetchGroups };
}

/**
 * Poll the sync status of a specific group.
 *
 * Polls every 5 seconds when the status is "syncing".
 * Stops polling when idle or errored.
 */
export function useSyncStatus(groupId: string | null): {
  status: string | null;
  progressCurrent: number | null;
  progressTotal: number | null;
  errorMessage: string | null;
  loading: boolean;
} {
  const [status, setStatus] = useState<string | null>(null);
  const [progressCurrent, setProgressCurrent] = useState<number | null>(null);
  const [progressTotal, setProgressTotal] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiFetch(`/api/groups/${groupId}/sync-status`);
      if (response.ok) {
        const data: SyncStatusResponse = await response.json();
        setStatus(data.status);
        setProgressCurrent(data.progress_current);
        setProgressTotal(data.progress_total);
        setErrorMessage(data.error_message);
      }
    } catch {
      // Silently fail polling
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useEffect(() => {
    if (!groupId) return;

    fetchStatus();

    intervalRef.current = setInterval(() => {
      fetchStatus();
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [groupId, fetchStatus]);

  // Stop polling when no longer syncing
  useEffect(() => {
    if (status && status !== "syncing" && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [status]);

  return { status, progressCurrent, progressTotal, errorMessage, loading };
}

/**
 * Trigger a sync operation for a group.
 */
export function useTriggerSync(): {
  trigger: (groupId: string) => Promise<void>;
  loading: boolean;
  error: string | null;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trigger = useCallback(async (groupId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/groups/${groupId}/sync`, {
        method: "POST",
      });
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Failed to trigger sync");
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { trigger, loading, error };
}

/**
 * Add a new group for the authenticated user.
 */
export function useAddGroup(): {
  addGroup: (email: string) => Promise<void>;
  loading: boolean;
  error: string | null;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addGroup = useCallback(async (email: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch("/api/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gmail_group_email: email }),
      });
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Failed to add group");
      }
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { addGroup, loading, error };
}
