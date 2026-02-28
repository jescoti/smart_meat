/**
 * MissingMessageGhost -- placeholder for ghost/missing messages in a thread.
 *
 * Renders a visually distinct dashed-border box indicating that the
 * original message was not found in the archive.
 */

export function MissingMessageGhost() {
  return (
    <div className="rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-4 text-gray-400">
      <p className="text-sm italic">
        This message was not found in the archive
      </p>
    </div>
  );
}
