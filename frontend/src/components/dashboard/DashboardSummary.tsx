/**
 * DashboardSummary component -- displays stats cards and recent items.
 *
 * Shows groups, threads, and nuggets counts along with recent threads
 * and recent nuggets lists. Handles loading, error, and empty states.
 */

import type { DashboardSummary as DashboardSummaryData } from "@/lib/hooks/useDashboard";

interface DashboardSummaryProps {
  data: DashboardSummaryData | null;
  isLoading: boolean;
  error: string | null;
}

export function DashboardSummary({
  data,
  isLoading,
  error,
}: DashboardSummaryProps) {
  if (isLoading) {
    return <p>Loading dashboard...</p>;
  }

  if (error) {
    return <p>{error}</p>;
  }

  if (!data) {
    return null;
  }

  return (
    <div>
      <div>
        <div>
          <p>{data.groups_count}</p>
          <p>Groups</p>
        </div>
        <div>
          <p>{data.threads_count}</p>
          <p>Threads</p>
        </div>
        <div>
          <p>{data.nuggets_count}</p>
          <p>Nuggets</p>
        </div>
      </div>

      <div>
        <h2>Recent Threads</h2>
        {data.recent_threads.length === 0 ? (
          <p>No recent threads</p>
        ) : (
          <ul>
            {data.recent_threads.map((thread, index) => (
              <li key={index}>
                <p>{thread.subject}</p>
                <p>{thread.group_name}</p>
                <p>{thread.message_count} messages</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <h2>Recent Nuggets</h2>
        {data.recent_nuggets.length === 0 ? (
          <p>No recent nuggets</p>
        ) : (
          <ul>
            {data.recent_nuggets.map((nugget, index) => (
              <li key={index}>
                <p>{nugget.content_preview}</p>
                {nugget.source_thread_subject && (
                  <p>From: {nugget.source_thread_subject}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
