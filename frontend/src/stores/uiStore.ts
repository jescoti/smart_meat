/**
 * UI state store.
 *
 * Manages transient UI state such as sidebar visibility.
 */

import { create } from "zustand";

interface UiState {
  /** Whether the sidebar navigation is open. */
  sidebarOpen: boolean;

  /** Toggle the sidebar between open and closed. */
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarOpen: false,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
