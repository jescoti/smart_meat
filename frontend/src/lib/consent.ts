/**
 * Consent management utilities for LLM processing opt-in.
 *
 * Provides functions to interact with the backend consent endpoints:
 * - getConsentStatus: check if the user has granted LLM consent
 * - grantConsent: record user's LLM consent
 * - revokeConsent: revoke user's LLM consent
 */

import { apiFetch } from "@/lib/api";

/** Shape of the consent status response from the backend. */
interface ConsentStatus {
  consented: boolean;
  consented_at: string | null;
}

/**
 * Fetch the current LLM consent status from the backend.
 *
 * @returns The consent status object.
 * @throws If the backend returns a non-200 response.
 */
export async function getConsentStatus(): Promise<ConsentStatus> {
  const resp = await apiFetch("/api/consent");

  if (!resp.ok) {
    throw new Error(`Failed to get consent status: ${resp.status}`);
  }

  return resp.json();
}

/**
 * Grant LLM consent by calling the backend.
 *
 * @returns `true` if consent was recorded, `false` otherwise.
 */
export async function grantConsent(): Promise<boolean> {
  try {
    const resp = await apiFetch("/api/consent", { method: "POST" });
    return resp.ok;
  } catch {
    return false;
  }
}

/**
 * Revoke LLM consent by calling the backend.
 *
 * @returns `true` if consent was revoked, `false` otherwise.
 */
export async function revokeConsent(): Promise<boolean> {
  try {
    const resp = await apiFetch("/api/consent", { method: "DELETE" });
    return resp.ok;
  } catch {
    return false;
  }
}
