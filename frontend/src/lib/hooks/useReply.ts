/**
 * useReply -- mutation hook for sending replies to threads.
 *
 * Calls POST /api/threads/:id/reply via apiFetch and manages
 * loading and error state.
 */

import { useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/**
 * Hook for sending a reply to a thread.
 *
 * @param threadId - The thread ID to reply to.
 * @returns An object with sendReply, isLoading, and error.
 */
export function useReply(threadId: string): {
  sendReply: (parentMessageId: string, bodyText: string) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
} {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendReply = useCallback(
    async (parentMessageId: string, bodyText: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiFetch(`/api/threads/${threadId}/reply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            parent_message_id: parentMessageId,
            body_text: bodyText,
          }),
        });
        if (!response.ok) {
          const data = await response.json();
          setError(data.message || "Failed to send reply");
          return false;
        }
        return true;
      } catch {
        setError("Network error");
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [threadId],
  );

  return { sendReply, isLoading, error };
}
