/**
 * ThreadViewer -- renders a full message hierarchy with visual nesting.
 *
 * Features:
 * - Visual indentation based on message depth
 * - Collapse/expand for thread branches
 * - Ghost messages rendered with MissingMessageGhost
 * - Regular messages rendered with MessageCard
 */

"use client";

import { useState, useMemo } from "react";
import type { ThreadMessageData } from "@/lib/hooks/useThreads";
import { MessageCard } from "./MessageCard";
import { MissingMessageGhost } from "./MissingMessageGhost";

interface ThreadViewerProps {
  messages: ThreadMessageData[];
  threadSubject: string;
}

/**
 * Determine which message IDs have children (for showing collapse buttons).
 */
function getParentIds(messages: ThreadMessageData[]): Set<string> {
  const parentIds = new Set<string>();
  for (const msg of messages) {
    if (msg.parent_message_id) {
      parentIds.add(msg.parent_message_id);
    }
  }
  return parentIds;
}

/**
 * Get the set of message IDs that are descendants of a given message.
 */
function getDescendantIds(
  messages: ThreadMessageData[],
  parentId: string,
): Set<string> {
  const descendants = new Set<string>();
  const queue = [parentId];

  while (queue.length > 0) {
    const currentId = queue.shift()!;
    for (const msg of messages) {
      if (msg.parent_message_id === currentId && !descendants.has(msg.id)) {
        descendants.add(msg.id);
        queue.push(msg.id);
      }
    }
  }

  return descendants;
}

export function ThreadViewer({ messages, threadSubject }: ThreadViewerProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());

  const parentIds = useMemo(() => getParentIds(messages), [messages]);

  // Determine which messages are hidden due to collapsed parents
  const hiddenIds = useMemo(() => {
    const hidden = new Set<string>();
    for (const collapsedId of collapsedIds) {
      const descendants = getDescendantIds(messages, collapsedId);
      for (const id of descendants) {
        hidden.add(id);
      }
    }
    return hidden;
  }, [collapsedIds, messages]);

  function toggleCollapse(messageId: string) {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }

  return (
    <div className="space-y-2">
      {messages.map((msg) => {
        if (hiddenIds.has(msg.id)) return null;

        const hasChildren = parentIds.has(msg.id);
        const isCollapsed = collapsedIds.has(msg.id);
        const indentPx = msg.depth * 24;

        return (
          <div
            key={msg.id}
            data-depth={msg.depth}
            style={{ marginLeft: `${indentPx}px` }}
          >
            <div className="flex items-start gap-2">
              {/* Collapse/expand toggle — only for messages with children */}
              {hasChildren && (
                <button
                  type="button"
                  onClick={() => toggleCollapse(msg.id)}
                  className="mt-3 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  aria-label={isCollapsed ? "Expand" : "Collapse"}
                >
                  <span className="inline-block w-4 text-center text-xs">
                    {isCollapsed ? "+" : "-"}
                  </span>
                </button>
              )}

              {/* Message content */}
              <div className="min-w-0 flex-1">
                {msg.is_ghost ? (
                  <MissingMessageGhost />
                ) : (
                  <MessageCard
                    message={msg}
                    threadSubject={threadSubject}
                  />
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
