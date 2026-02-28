/**
 * Thread Detail page -- renders the full message hierarchy.
 *
 * Uses the ThreadViewer component to display messages with
 * correct nesting, collapse/expand, and ghost message handling.
 */

"use client";

import { useParams } from "next/navigation";
import { useThreadDetail } from "@/lib/hooks/useThreads";
import { ThreadViewer } from "@/components/thread/ThreadViewer";

export default function ThreadDetailPage() {
  const params = useParams();
  const threadId = params.threadId as string;

  const { thread, messages, isLoading, error } = useThreadDetail(threadId);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-4xl p-6">
        <p className="text-gray-500">Loading thread...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto max-w-4xl p-6">
        <p className="text-red-600">{error}</p>
      </main>
    );
  }

  if (!thread) {
    return null;
  }

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">{thread.subject}</h1>
      <ThreadViewer messages={messages} threadSubject={thread.subject} />
    </main>
  );
}
