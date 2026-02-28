/**
 * Tests for the DashboardSummary component.
 *
 * TDD RED phase -- tests written before implementation.
 * Tests loading, error, empty, and populated states.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { DashboardSummary as DashboardSummaryData } from "@/lib/hooks/useDashboard";
import { DashboardSummary } from "./DashboardSummary";

const MOCK_DATA: DashboardSummaryData = {
  groups_count: 3,
  threads_count: 25,
  nuggets_count: 12,
  recent_threads: [
    {
      subject: "Weekly Meeting Notes",
      group_name: "Engineering",
      message_count: 10,
      last_activity: "2024-06-15T12:00:00+00:00",
    },
    {
      subject: "Design Review",
      group_name: "Product",
      message_count: 5,
      last_activity: "2024-06-14T10:00:00+00:00",
    },
  ],
  recent_nuggets: [
    {
      content_preview: "Testing best practices include writing tests first.",
      source_thread_subject: "Testing Discussion",
    },
    {
      content_preview: "Always use dependency injection for services.",
      source_thread_subject: null,
    },
  ],
};

describe("DashboardSummary", () => {
  describe("loading state", () => {
    it("shows loading indicator when isLoading is true", () => {
      render(
        <DashboardSummary data={null} isLoading={true} error={null} />,
      );

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("shows error message when error is present", () => {
      render(
        <DashboardSummary
          data={null}
          isLoading={false}
          error="Failed to load dashboard"
        />,
      );

      expect(
        screen.getByText(/failed to load dashboard/i),
      ).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("shows empty state when data has zero counts", () => {
      const emptyData: DashboardSummaryData = {
        groups_count: 0,
        threads_count: 0,
        nuggets_count: 0,
        recent_threads: [],
        recent_nuggets: [],
      };

      render(
        <DashboardSummary data={emptyData} isLoading={false} error={null} />,
      );

      const zeros = screen.getAllByText("0");
      expect(zeros).toHaveLength(3);
    });
  });

  describe("populated state", () => {
    it("shows groups count", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("Groups")).toBeInTheDocument();
    });

    it("shows threads count", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText("25")).toBeInTheDocument();
      expect(screen.getByText("Threads")).toBeInTheDocument();
    });

    it("shows nuggets count", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText("12")).toBeInTheDocument();
      expect(screen.getByText("Nuggets")).toBeInTheDocument();
    });

    it("shows recent thread subjects", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText("Weekly Meeting Notes")).toBeInTheDocument();
      expect(screen.getByText("Design Review")).toBeInTheDocument();
    });

    it("shows recent thread group names", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText(/engineering/i)).toBeInTheDocument();
      expect(screen.getByText(/product/i)).toBeInTheDocument();
    });

    it("shows recent thread message counts", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(screen.getByText(/10 messages/i)).toBeInTheDocument();
      expect(screen.getByText(/5 messages/i)).toBeInTheDocument();
    });

    it("shows recent nugget content previews", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(
        screen.getByText(
          "Testing best practices include writing tests first.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          "Always use dependency injection for services.",
        ),
      ).toBeInTheDocument();
    });

    it("shows source thread subject for nuggets that have one", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(
        screen.getByText(/testing discussion/i),
      ).toBeInTheDocument();
    });

    it("shows recent threads heading", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(
        screen.getByRole("heading", { name: /recent threads/i }),
      ).toBeInTheDocument();
    });

    it("shows recent nuggets heading", () => {
      render(
        <DashboardSummary data={MOCK_DATA} isLoading={false} error={null} />,
      );

      expect(
        screen.getByRole("heading", { name: /recent nuggets/i }),
      ).toBeInTheDocument();
    });
  });

  describe("data is null", () => {
    it("does not render content when data is null and not loading", () => {
      render(
        <DashboardSummary data={null} isLoading={false} error={null} />,
      );

      expect(screen.queryByText(/groups/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/threads/i)).not.toBeInTheDocument();
    });
  });
});
