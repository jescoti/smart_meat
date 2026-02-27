/**
 * LoadingState — spinner shown while async content is being fetched.
 *
 * Accessible: uses role="status" and a visually hidden label so screen
 * readers announce the loading state without requiring sighted users to
 * see extra text.
 */

export function LoadingState() {
  return (
    <div
      role="status"
      className="flex items-center justify-center py-12"
      aria-label="Loading"
    >
      {/* Animated spinner ring */}
      <span
        className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600"
        aria-hidden="true"
      />
      {/* Screen-reader only label */}
      <span className="sr-only">Loading…</span>
    </div>
  );
}
