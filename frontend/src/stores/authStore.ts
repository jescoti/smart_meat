/**
 * Authentication store.
 *
 * Stores only the user's identity fields — NEVER raw access tokens or refresh
 * tokens.  Token management is handled server-side via HTTP-only cookies.
 */

import { create } from "zustand";

interface AuthUser {
  id: string;
  name: string;
  email: string;
  avatarUrl: string | null;
}

interface AuthState {
  /** Currently authenticated user, or null when unauthenticated. */
  user: AuthUser | null;

  /**
   * Derived flag — true when user is non-null.
   * Components should prefer this over `user !== null` for clarity.
   */
  isAuthenticated: boolean;

  /** Set the active user after successful authentication. */
  setUser: (user: AuthUser) => void;

  /** Clear the user on sign-out or session expiry. */
  clearUser: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  isAuthenticated: false,

  setUser: (user) => set({ user, isAuthenticated: true }),

  clearUser: () => set({ user: null, isAuthenticated: false }),
}));
