/**
 * Groups page -- lists user's Google Groups with sync management.
 *
 * Features:
 * - List all groups with sync status indicators
 * - Add new groups via email input
 * - Trigger sync per group
 * - Show sync progress and errors
 */

"use client";

import { useState } from "react";
import {
  useGroups,
  useTriggerSync,
  useAddGroup,
} from "@/lib/hooks/useSync";

export default function GroupsPage() {
  const { groups, loading, error, refresh } = useGroups();
  const { trigger, loading: syncLoading } = useTriggerSync();
  const { addGroup, loading: addLoading, error: addError } = useAddGroup();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newGroupEmail, setNewGroupEmail] = useState("");

  async function handleSync(groupId: string) {
    await trigger(groupId);
    await refresh();
  }

  async function handleAddGroup() {
    if (!newGroupEmail.trim()) return;
    await addGroup(newGroupEmail.trim());
    setNewGroupEmail("");
    setShowAddForm(false);
    await refresh();
  }

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Groups</h1>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          Add Group
        </button>
      </div>

      {showAddForm && (
        <div className="mb-6 rounded-lg border border-gray-200 p-4">
          <input
            type="email"
            value={newGroupEmail}
            onChange={(e) => setNewGroupEmail(e.target.value)}
            placeholder="Group email (e.g. group@googlegroups.com)"
            className="mb-2 w-full rounded border border-gray-300 px-3 py-2"
          />
          <button
            onClick={handleAddGroup}
            disabled={addLoading}
            className="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:opacity-50"
          >
            Submit
          </button>
          {addError && (
            <p className="mt-2 text-sm text-red-600">{addError}</p>
          )}
        </div>
      )}

      {loading && <p className="text-gray-500">Loading groups...</p>}

      {error && (
        <p className="text-red-600">{error}</p>
      )}

      {!loading && !error && groups.length === 0 && (
        <p className="text-gray-500">No groups yet. Add a Google Group to get started.</p>
      )}

      {groups.length > 0 && (
        <ul className="space-y-4">
          {groups.map((group) => (
            <li
              key={group.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 p-4"
            >
              <div>
                <p className="font-medium">{group.gmail_group_email}</p>
                <p className="text-sm text-gray-500">
                  Status: {group.sync_status}
                </p>
              </div>
              <button
                onClick={() => handleSync(group.id)}
                disabled={syncLoading || group.sync_status === "syncing"}
                className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Sync
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
