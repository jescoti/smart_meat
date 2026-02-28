"use client";

/**
 * Dashboard page -- landing page showing groups, threads, and nuggets at a glance.
 *
 * Uses the useDashboard hook to fetch summary data and renders
 * the DashboardSummary component.
 */

import { useDashboard } from "@/lib/hooks/useDashboard";
import { DashboardSummary } from "@/components/dashboard/DashboardSummary";

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();

  return (
    <main>
      <h1>Dashboard</h1>
      <DashboardSummary data={data} isLoading={isLoading} error={error} />
    </main>
  );
}
