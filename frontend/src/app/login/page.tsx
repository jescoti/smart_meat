/**
 * Login page — presents a "Sign in with Google" button.
 *
 * Fetches the OAuth authorization URL from the backend and redirects
 * the browser when the user clicks the button.
 */

"use client";

import { getLoginUrl } from "@/lib/auth";

export default function LoginPage() {
  async function handleSignIn() {
    const url = await getLoginUrl();
    window.location.href = url;
  }

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="mb-8 text-3xl font-bold">Smart Meat</h1>
        <button
          onClick={handleSignIn}
          className="rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700"
        >
          Sign in with Google
        </button>
      </div>
    </main>
  );
}
