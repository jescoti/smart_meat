/**
 * Hooks for thread listing and thread detail.
 *
 * Provides useThreadList and useThreadDetail hooks for fetching
 * paginated thread lists and full thread message hierarchies.
 */

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/** Shape of a thread object returned from the API. */
export interface ThreadData {
  id: string;
  subject: string;
  message_count: number;
  participant_count: number;
  last_message_at: string | null;
  created_at: string | null;
}

/** Shape of a message in a thread hierarchy. */
export interface ThreadMessageData {
  id: string;
  sender_email: string;
  sender_name: string | null;
  subject: string;
  body_text: string | null;
  body_html: string | null;
  gmail_date: string | null;
  depth: number;
  is_ghost: boolean;
  parent_message_id: string | null;
}

/** Response shape from the thread list endpoint. */
interface ThreadListResponse {
  threads: ThreadData[];
  total: number;
  page: number;
  per_page: number;
}

/** Response shape from the thread detail endpoint. */
interface ThreadDetailResponse {
  thread: ThreadData;
  messages: ThreadMessageData[];
}

/**
 * Fetch and manage a paginated list of threads for a group.
 */
export function useThreadList(
  groupId: string,
  page: number = 1,
  perPage: number = 20,
): {
  threads: ThreadData[];
  total: number;
  page: number;
  perPage: number;
  isLoading: boolean;
  error: string | null;
} {
  const [threads, setThreads] = useState<ThreadData[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(page);
  const [currentPerPage, setCurrentPerPage] = useState(perPage);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchThreads = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch(
        `/api/groups/${groupId}/threads?page=${page}&per_page=${perPage}`,
      );
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Failed to load threads");
        return;
      }
      const data: ThreadListResponse = await response.json();
      setThreads(data.threads);
      setTotal(data.total);
      setCurrentPage(data.page);
      setCurrentPerPage(data.per_page);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, [groupId, page, perPage]);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  return {
    threads,
    total,
    page: currentPage,
    perPage: currentPerPage,
    isLoading,
    error,
  };
}

/**
 * Fetch thread detail with full message hierarchy.
 */
export function useThreadDetail(
  threadId: string | null,
): {
  thread: ThreadData | null;
  messages: ThreadMessageData[];
  isLoading: boolean;
  error: string | null;
} {
  const [thread, setThread] = useState<ThreadData | null>(null);
  const [messages, setMessages] = useState<ThreadMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/threads/${threadId}`);
      if (!response.ok) {
        const data = await response.json();
        setError(data.message || "Failed to load thread");
        return;
      }
      const data: ThreadDetailResponse = await response.json();
      setThread(data.thread);
      setMessages(data.messages);
    } catch {
      setError("Network error");
    } finally {
      setIsLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (threadId) {
      fetchDetail();
    }
  }, [threadId, fetchDetail]);

  return { thread, messages, isLoading, error };
}
