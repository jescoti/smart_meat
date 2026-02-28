/**
 * Consent page -- asks the user to opt in to LLM processing.
 *
 * Explains that email content will be sent to the Claude API for
 * summarization and knowledge extraction, then presents "I Agree"
 * and "Decline" options.
 */

"use client";

import { grantConsent } from "@/lib/consent";

export default function ConsentPage() {
  async function handleAgree() {
    const ok = await grantConsent();
    if (ok) {
      window.location.href = "/dashboard";
    }
  }

  function handleDecline() {
    window.location.href = "/dashboard";
  }

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="max-w-lg text-center">
        <h1 className="mb-6 text-2xl font-bold">LLM Processing Consent</h1>
        <p className="mb-6 text-gray-600">
          To provide summarization and knowledge extraction features, your email
          content will be processed by an AI language model (Claude API). No
          data is shared with third parties beyond this processing.
        </p>
        <div className="flex justify-center gap-4">
          <button
            onClick={handleAgree}
            className="rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700"
          >
            I Agree
          </button>
          <button
            onClick={handleDecline}
            className="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 hover:bg-gray-50"
          >
            Decline
          </button>
        </div>
      </div>
    </main>
  );
}
