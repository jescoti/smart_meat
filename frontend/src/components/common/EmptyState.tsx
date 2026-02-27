/**
 * EmptyState — displayed when a list or section has no content.
 *
 * Props:
 *   icon        Optional React node to render above the title.
 *   title       Short heading (required).
 *   description Supporting text (required).
 */

import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description: string;
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      {icon != null && <div className="text-gray-400">{icon}</div>}
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  );
}
