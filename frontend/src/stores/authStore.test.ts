/**
 * Tests for authStore — written FIRST (TDD Red phase).
 *
 * Verifies that the store manages user identity without ever storing raw
 * access tokens or refresh tokens.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "./authStore";

const MOCK_USER = {
  id: "user-1",
  name: "Alice Smith",
  email: "alice@example.com",
  avatarUrl: "https://example.com/avatar.png",
};

describe("authStore", () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useAuthStore.setState({ user: null });
  });

  describe("initial state", () => {
    it("has null user by default", () => {
      const { user } = useAuthStore.getState();
      expect(user).toBeNull();
    });

    it("is not authenticated by default", () => {
      const { isAuthenticated } = useAuthStore.getState();
      expect(isAuthenticated).toBe(false);
    });
  });

  describe("setUser", () => {
    it("stores the user object", () => {
      const { setUser } = useAuthStore.getState();
      setUser(MOCK_USER);

      const { user } = useAuthStore.getState();
      expect(user).toEqual(MOCK_USER);
    });

    it("sets isAuthenticated to true when user is set", () => {
      const { setUser } = useAuthStore.getState();
      setUser(MOCK_USER);

      const { isAuthenticated } = useAuthStore.getState();
      expect(isAuthenticated).toBe(true);
    });

    it("allows avatarUrl to be null", () => {
      const { setUser } = useAuthStore.getState();
      setUser({ ...MOCK_USER, avatarUrl: null });

      const { user } = useAuthStore.getState();
      expect(user?.avatarUrl).toBeNull();
    });
  });

  describe("clearUser", () => {
    it("sets user back to null", () => {
      const { setUser, clearUser } = useAuthStore.getState();
      setUser(MOCK_USER);
      clearUser();

      const { user } = useAuthStore.getState();
      expect(user).toBeNull();
    });

    it("sets isAuthenticated to false after clearUser", () => {
      const { setUser, clearUser } = useAuthStore.getState();
      setUser(MOCK_USER);
      clearUser();

      const { isAuthenticated } = useAuthStore.getState();
      expect(isAuthenticated).toBe(false);
    });
  });

  describe("token security", () => {
    it("does not expose accessToken property on the store state", () => {
      const state = useAuthStore.getState() as Record<string, unknown>;
      // Raw tokens must NEVER be stored in the auth store
      expect("accessToken" in state).toBe(false);
      expect("refreshToken" in state).toBe(false);
      expect("token" in state).toBe(false);
    });
  });
});
