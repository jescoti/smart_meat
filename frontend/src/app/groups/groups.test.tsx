/**
 * Tests for the Groups page.
 *
 * TDD RED phase -- tests written before implementation.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/hooks/useSync", () => ({
  useGroups: vi.fn(),
  useSyncStatus: vi.fn(),
  useTriggerSync: vi.fn(),
  useAddGroup: vi.fn(),
}));

import GroupsPage from "./page";
import {
  useGroups,
  useSyncStatus,
  useTriggerSync,
  useAddGroup,
} from "@/lib/hooks/useSync";

const mockUseGroups = vi.mocked(useGroups);
const mockUseSyncStatus = vi.mocked(useSyncStatus);
const mockUseTriggerSync = vi.mocked(useTriggerSync);
const mockUseAddGroup = vi.mocked(useAddGroup);

beforeEach(() => {
  mockUseGroups.mockReturnValue({
    groups: [],
    loading: false,
    error: null,
    refresh: vi.fn(),
  });

  mockUseSyncStatus.mockReturnValue({
    status: "idle",
    progressCurrent: null,
    progressTotal: null,
    errorMessage: null,
    loading: false,
  });

  mockUseTriggerSync.mockReturnValue({
    trigger: vi.fn(),
    loading: false,
    error: null,
  });

  mockUseAddGroup.mockReturnValue({
    addGroup: vi.fn(),
    loading: false,
    error: null,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GroupsPage", () => {
  it("renders a page heading", () => {
    render(<GroupsPage />);
    expect(screen.getByRole("heading", { name: /groups/i })).toBeInTheDocument();
  });

  it("renders an add group button", () => {
    render(<GroupsPage />);
    expect(
      screen.getByRole("button", { name: /add group/i }),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseGroups.mockReturnValue({
      groups: [],
      loading: true,
      error: null,
      refresh: vi.fn(),
    });

    render(<GroupsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseGroups.mockReturnValue({
      groups: [],
      loading: false,
      error: "Failed to load groups",
      refresh: vi.fn(),
    });

    render(<GroupsPage />);
    expect(screen.getByText(/failed to load groups/i)).toBeInTheDocument();
  });

  it("shows empty state when no groups", () => {
    render(<GroupsPage />);
    expect(screen.getByText(/no groups/i)).toBeInTheDocument();
  });

  it("renders group list", () => {
    mockUseGroups.mockReturnValue({
      groups: [
        {
          id: "group-1",
          gmail_group_email: "test@googlegroups.com",
          display_name: "test@googlegroups.com",
          sync_status: "idle",
          sync_error_message: null,
          sync_progress_current: null,
          sync_progress_total: null,
        },
      ],
      loading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<GroupsPage />);
    expect(screen.getByText("test@googlegroups.com")).toBeInTheDocument();
  });

  it("shows sync button for each group", () => {
    mockUseGroups.mockReturnValue({
      groups: [
        {
          id: "group-1",
          gmail_group_email: "test@googlegroups.com",
          display_name: "test@googlegroups.com",
          sync_status: "idle",
          sync_error_message: null,
          sync_progress_current: null,
          sync_progress_total: null,
        },
      ],
      loading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<GroupsPage />);
    expect(
      screen.getByRole("button", { name: /sync/i }),
    ).toBeInTheDocument();
  });

  it("calls trigger sync when sync button is clicked", async () => {
    const mockTrigger = vi.fn();
    mockUseTriggerSync.mockReturnValue({
      trigger: mockTrigger,
      loading: false,
      error: null,
    });

    mockUseGroups.mockReturnValue({
      groups: [
        {
          id: "group-1",
          gmail_group_email: "test@googlegroups.com",
          display_name: "test@googlegroups.com",
          sync_status: "idle",
          sync_error_message: null,
          sync_progress_current: null,
          sync_progress_total: null,
        },
      ],
      loading: false,
      error: null,
      refresh: vi.fn(),
    });

    const user = userEvent.setup();
    render(<GroupsPage />);

    await user.click(screen.getByRole("button", { name: /sync/i }));

    expect(mockTrigger).toHaveBeenCalledWith("group-1");
  });

  it("shows input when add group button is clicked", async () => {
    const user = userEvent.setup();
    render(<GroupsPage />);

    await user.click(screen.getByRole("button", { name: /add group/i }));

    expect(screen.getByPlaceholderText(/group email/i)).toBeInTheDocument();
  });

  it("calls addGroup when form is submitted", async () => {
    const mockAdd = vi.fn();
    mockUseAddGroup.mockReturnValue({
      addGroup: mockAdd,
      loading: false,
      error: null,
    });

    const user = userEvent.setup();
    render(<GroupsPage />);

    await user.click(screen.getByRole("button", { name: /add group/i }));

    const input = screen.getByPlaceholderText(/group email/i);
    await user.type(input, "new-group@googlegroups.com");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(mockAdd).toHaveBeenCalledWith("new-group@googlegroups.com");
  });
});
