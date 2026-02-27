/**
 * Tests for uiStore — written FIRST (TDD Red phase).
 *
 * Verifies sidebar toggle behaviour.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useUiStore } from "./uiStore";

describe("uiStore", () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useUiStore.setState({ sidebarOpen: false });
  });

  describe("initial state", () => {
    it("has sidebarOpen false by default", () => {
      const { sidebarOpen } = useUiStore.getState();
      expect(sidebarOpen).toBe(false);
    });
  });

  describe("toggleSidebar", () => {
    it("toggles sidebarOpen from false to true", () => {
      const { toggleSidebar } = useUiStore.getState();
      toggleSidebar();

      const { sidebarOpen } = useUiStore.getState();
      expect(sidebarOpen).toBe(true);
    });

    it("toggles sidebarOpen from true back to false", () => {
      useUiStore.setState({ sidebarOpen: true });
      const { toggleSidebar } = useUiStore.getState();
      toggleSidebar();

      const { sidebarOpen } = useUiStore.getState();
      expect(sidebarOpen).toBe(false);
    });

    it("toggles twice to return to original state", () => {
      const { toggleSidebar } = useUiStore.getState();
      toggleSidebar();
      toggleSidebar();

      const { sidebarOpen } = useUiStore.getState();
      expect(sidebarOpen).toBe(false);
    });
  });
});
