/**
 * SyncProgress -- displays a progress bar with percentage for sync operations.
 *
 * Accessible via role="progressbar" with appropriate aria attributes.
 */

interface SyncProgressProps {
  /** Current progress count. */
  current: number | null;
  /** Total count for progress. */
  total: number | null;
  /** Optional status text to display below the bar. */
  statusText?: string;
}

export default function SyncProgress({
  current,
  total,
  statusText,
}: SyncProgressProps) {
  const safeCurrent = current ?? 0;
  const safeTotal = total ?? 0;
  const percentage = safeTotal > 0 ? Math.round((safeCurrent / safeTotal) * 100) : 0;

  return (
    <div className="w-full">
      <div
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-4 w-full overflow-hidden rounded-full bg-gray-200"
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-sm text-gray-600">
        <span>{percentage}%</span>
        {statusText && <span>{statusText}</span>}
      </div>
    </div>
  );
}
