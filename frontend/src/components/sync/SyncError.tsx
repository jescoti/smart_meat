/**
 * SyncError -- displays a sync error message with a retry button.
 */

interface SyncErrorProps {
  /** The error message to display. */
  message: string;
  /** Callback invoked when the user clicks Retry. */
  onRetry: () => void;
}

export default function SyncError({ message, onRetry }: SyncErrorProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="mb-2 font-semibold text-red-800">Sync Error</p>
      <p className="mb-3 text-sm text-red-700">{message}</p>
      <button
        onClick={onRetry}
        className="rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
      >
        Retry
      </button>
    </div>
  );
}
